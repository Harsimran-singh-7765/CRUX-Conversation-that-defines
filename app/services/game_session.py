import logging
import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from uuid import UUID
from app.schemas.game_schemas import GameSession, Scenario, ConversationEntry
from app.db import db_service
from app.services.deepgram_service import deepgram_service 
from app.services import llm_service

logger = logging.getLogger(__name__)

class GameSessionManager:
    """
    Manages the entire lifecycle of a single game session over a WebSocket.
    """

    def __init__(self, websocket: WebSocket, session_id: UUID):
        self.websocket = websocket
        self.session_id = session_id
        self.session: GameSession | None = None
        self.scenario: Scenario | None = None
        self.transcriber = None
        self.is_active = True

    def _clean_text_for_tts(self, text: str) -> str:
        """Removes characters that should not be spoken by TTS."""
        logger.info(f"[{self.session_id}] Cleaning text for TTS...")
        
        cleaned_text = text.replace("*", "") 
        cleaned_text = cleaned_text.replace("#", "")
        
        logger.info(f"[{self.session_id}] Cleaned text: '{cleaned_text[:60]}...'")
        return cleaned_text
    
    def _split_angry_response(self, text: str) -> list[str]:
        """
        Splits text by 'BREAK' keyword for angry spam streak effect.
        Returns list of individual messages.
        """
        if "BREAK" not in text:
            return [text]
        
        # Split by BREAK and clean up empty strings
        messages = [msg.strip() for msg in text.split("BREAK") if msg.strip()]
        logger.info(f"[{self.session_id}] Split angry response into {len(messages)} messages")
        return messages
    
    async def _load_session_data(self, retries=3, delay=0.5) -> bool:
        logger.info(f"[{self.session_id}] Loading session data...")
        for attempt in range(retries):
            self.session = await db_service.db_get_game_session(self.session_id)
            if self.session:
                self.scenario = await db_service.db_get_scenario(self.session.scenario_id)
                if self.scenario:
                    logger.info(f"[{self.session_id}] Data loaded for scenario: {self.scenario.title}")
                    return True
                logger.error(f"[{self.session_id}] Scenario missing: {self.session.scenario_id}")
                return False

            logger.warning(f"[{self.session_id}] Session not found, retry {attempt+1}")
            await asyncio.sleep(delay)

        logger.error(f"[{self.session_id}] Failed to load session after retries.")
        return False

    async def _send_json(self, data: dict):
        if self.is_active:
            logger.debug(f"[{self.session_id}] Sending JSON to client: {json.dumps(data)}")
            await self.websocket.send_text(json.dumps(data))

    async def _generate_audio_for_message(self, text: str, gender: str) -> bytes:
        """
        Generates complete audio for a single message.
        Returns audio as bytes.
        """
        logger.info(f"[{self.session_id}] Generating audio for: '{text[:50]}...'")
        audio_chunks = []
        
        try:
            async for chunk in deepgram_service.text_to_speech_stream(text, gender):
                audio_chunks.append(chunk)
            
            # Combine all chunks into single audio blob
            full_audio = b''.join(audio_chunks)
            logger.info(f"[{self.session_id}] Generated {len(full_audio)} bytes of audio")
            return full_audio
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Audio generation error: {e}")
            return b''

    async def _stream_angry_spam(self, messages: list[str], gender: str):
        """
        Sends angry spam streak: multiple messages with audio rapidly.
        """
        logger.info(f"[{self.session_id}] 🔥 ANGRY SPAM ACTIVATED! {len(messages)} messages incoming!")
        
        # Signal spam streak is starting
        await self._send_json({
            "status": "angry_spam_streak",
            "message_count": len(messages)
        })
        
        # Generate audio for all messages in parallel
        audio_tasks = [
            self._generate_audio_for_message(self._clean_text_for_tts(msg), gender) 
            for msg in messages
        ]
        audio_array = await asyncio.gather(*audio_tasks)
        
        # Send all messages and audio to frontend
        for idx, (message, audio) in enumerate(zip(messages, audio_array)):
            if not self.is_active:
                break
                
            logger.info(f"[{self.session_id}] 💥 Spam #{idx+1}/{len(messages)}: '{message[:40]}...'")
            
            # Send text
            await self._send_json({
                "status": "spam_message",
                "index": idx,
                "total": len(messages),
                "text": message
            })
            
            # Send audio
            if audio:
                await self.websocket.send_bytes(audio)
        
        # Signal spam streak is complete
        await self._send_json({"status": "spam_streak_complete"})
        logger.info(f"[{self.session_id}] ✅ Angry spam streak complete")

    async def _stream_ai_audio(self, original_text: str, gender: str):
        """
        Streams AI audio. Detects BREAK keyword for angry spam mode.
        IMPORTANT: Pass ORIGINAL text, not cleaned text!
        """
        logger.info(f"[{self.session_id}] Processing AI response: '{original_text[:80]}...'")
        
        # 🔥 CRITICAL: Check for BREAK in ORIGINAL text BEFORE cleaning
        if "BREAK" in original_text:
            logger.warning(f"[{self.session_id}] ⚠️ BREAK detected in original text! Triggering spam mode...")
            messages = self._split_angry_response(original_text)
            await self._stream_angry_spam(messages, gender)
            return
        
        # Normal single-message audio streaming
        logger.info(f"[{self.session_id}] Normal mode - streaming single message")
        await self._send_json({"status": "ai_speaking"})

        try:
            # Clean text ONLY for TTS
            cleaned_text = self._clean_text_for_tts(original_text)
            
            async for chunk in deepgram_service.text_to_speech_stream(cleaned_text, gender):
                if self.is_active:
                    logger.debug(f"[{self.session_id}] Sending audio chunk to client: {len(chunk)} bytes")
                    await self.websocket.send_bytes(chunk)

            await self._send_json({"status": "ai_finished_speaking"})
            logger.info(f"[{self.session_id}] Finished streaming AI audio.")

        except Exception as e:
            logger.error(f"[{self.session_id}] TTS error: {e}")
            await self._send_json({"status": "error", "message": "AI voice failed"})

    async def _start_stt(self):
        """Start Deepgram real-time transcription."""
        logger.info(f"[{self.session_id}] Starting STT...")
        self.transcriber = deepgram_service.get_live_transcriber()
        self.transcriber.start()

    async def _handle_user_speech(self, audio_chunk: bytes):
        """Send audio data to the transcriber."""
        if self.transcriber and self.transcriber._is_active:
            logger.debug(f"[{self.session_id}] Sending audio chunk to STT: {len(audio_chunk)} bytes")
            await asyncio.to_thread(self.transcriber.send, audio_chunk)

    async def _stop_stt_and_process_transcript(self):
        """Stop STT and process the final transcript."""
        if not self.transcriber:
            return

        logger.info(f"[{self.session_id}] Stopping STT...")
        
        transcript = self.transcriber.stop()
        self.transcriber = None

        logger.debug(f"[{self.session_id}] Raw transcript from Deepgram: '{transcript}'")

        if transcript and isinstance(transcript, str) and transcript.strip():
            await self._process_user_transcript(transcript)
        else:
            logger.warning(f"[{self.session_id}] Empty or invalid transcript.")
            await self._send_json({"status": "ai_finished_speaking"})

    async def _process_user_transcript(self, text: str):
        if not self.session or not self.scenario:
            logger.error(f"[{self.session_id}] Error: _process_user_transcript called with no session or scenario.")
            return
            
        logger.info(f"[{self.session_id}] User said: '{text}'")
        
        await self._send_json({"status": "user_response_text", "text": text})

        self.session.conversation_history.append(ConversationEntry(role="user", message=text))
        await self._send_json({"status": "ai_thinking"})

        try:
            response = await asyncio.to_thread(
                llm_service.get_ai_response, self.session, self.scenario
            )
            logger.info(f"[{self.session_id}] AI response received from LLM: '{response}'")
            
            self.session.conversation_history.append(ConversationEntry(role="ai", message=response))
            
            # Send original response (with BREAK) to UI for display
            await self._send_json({"status": "ai_response_text", "text": response})
            
            # 🔥 CRITICAL: Pass ORIGINAL response (with BREAK intact) to audio streaming
            await self._stream_ai_audio(response, self.scenario.character_gender)

        except Exception as e:
            logger.error(f"[{self.session_id}] AI response error: {e}", exc_info=True)
            await self._send_json({"status": "error", "message": "AI processing failed"})

    async def _handle_end_game(self):
        if not self.session or not self.scenario:
             logger.error(f"[{self.session_id}] Error: _handle_end_game called with no session or scenario.")
             return
        logger.info(f"[{self.session_id}] User ended the game.")
        await self._send_json({"status": "evaluating"})
        try:
            result = await asyncio.to_thread(
                llm_service.evaluate_conversation, self.session, self.scenario
            )
            logger.info(f"[{self.session_id}] Evaluation result: Score={result.score}, Justification='{result.justification}'")
            await db_service.db_end_game_session(
                session_id=self.session.session_id,
                score=result.score,
                justification=result.justification
            )
            await self._send_json({
                "status": "game_over",
                "score": result.score,
                "justification": result.justification
            })
        except Exception as e:
            logger.error(f"[{self.session_id}] Evaluation error: {e}", exc_info=True)
            await self._send_json({"status": "error", "message": "Game result failed"})
        finally:
            self.is_active = False

    async def run(self):
        """Main entry point for the game session."""
        if not await self._load_session_data() or not self.session or not self.scenario:
            await self.websocket.close(code=1008, reason="Invalid session")
            self.is_active = False
            return
        
        # Pass original message for first audio
        await self._stream_ai_audio(self.session.conversation_history[0].message, self.scenario.character_gender)

        while self.is_active:
            try:
                data = await self.websocket.receive()
                logger.debug(f"[{self.session_id}] Received data type: {data['type']}")
                if data["type"] == "websocket.receive":
                    if "text" in data and data["text"] is not None:
                        logger.debug(f"[{self.session_id}] Received JSON string from client: {data['text']}")
                        msg = json.loads(data["text"])
                        action = msg.get("action")
                        if action == "start_speaking":
                            logger.info(f"[{self.session_id}] start_speaking")
                            await self._start_stt()
                        elif action == "stop_speaking":
                            logger.info(f"[{self.session_id}] stop_speaking")
                            await self._stop_stt_and_process_transcript()
                        elif action == "end_game":
                            await self._handle_end_game()
                    elif "bytes" in data:
                        logger.debug(f"[{self.session_id}] Received audio bytes from client: {len(data['bytes'])}")
                        await self._handle_user_speech(data["bytes"])
            except WebSocketDisconnect:
                logger.info(f"[{self.session_id}] WebSocket disconnected.")
                self.is_active = False
            except Exception as e:
                logger.error(f"[{self.session_id}] Unhandled error: {e}", exc_info=True)
                self.is_active = False
        
        if self.transcriber:
            try:
                if hasattr(self.transcriber, '_is_active') and self.transcriber._is_active:
                    self.transcriber.stop()
            except Exception as e:
                logger.error(f"[{self.session_id}] Error during cleanup: {e}")
            finally:
                self.transcriber = None
        logger.info(f"[{self.session_id}] Game session ended.")