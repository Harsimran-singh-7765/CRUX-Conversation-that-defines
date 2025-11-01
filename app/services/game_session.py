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
            await self.websocket.send_text(json.dumps(data))

    async def _stream_ai_audio(self, text: str, gender: str):
        logger.info(f"[{self.session_id}] Streaming AI audio: '{text[:50]}...'")
        await self._send_json({"status": "ai_speaking"})

        try:
            async for chunk in deepgram_service.text_to_speech_stream(text, gender):
                if self.is_active:
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

        # start() is synchronous, just call it
        if hasattr(self.transcriber, "start"):
            self.transcriber.start()

    async def _handle_user_speech(self, audio_chunk: bytes):
        """Send audio data to the transcriber."""
        if self.transcriber and hasattr(self.transcriber, "send"):
            # send() is synchronous in Deepgram SDK
            self.transcriber.send(audio_chunk)

    async def _stop_stt_and_process_transcript(self):
        """Stop STT and process the final transcript."""
        if not self.transcriber:
            return

        logger.info(f"[{self.session_id}] Stopping STT...")

        try:
            # stop() is synchronous and returns the transcript string
            transcript = self.transcriber.stop()
            self.transcriber = None

            # Only process if we got a valid transcript string
            if transcript and isinstance(transcript, str) and transcript.strip():
                await self._process_user_transcript(transcript)
            else:
                logger.warning(f"[{self.session_id}] Empty or invalid transcript: {transcript}")
                await self._send_json({"status": "ai_finished_speaking"})
                
        except Exception as e:
            logger.error(f"[{self.session_id}] Error stopping STT: {e}", exc_info=True)
            self.transcriber = None
            await self._send_json({"status": "error", "message": "Speech recognition failed"})

    async def _process_user_transcript(self, text: str):
        if not self.session or not self.scenario:
            logger.error(f"[{self.session_id}] Error: _process_user_transcript called with no session or scenario.")
            return

        logger.info(f"[{self.session_id}] User said: '{text}'")

        self.session.conversation_history.append(ConversationEntry(role="user", message=text))
        await self._send_json({"status": "ai_thinking"})

        try:
            response = await llm_service.get_ai_response(self.session, self.scenario)
            self.session.conversation_history.append(ConversationEntry(role="ai", message=response))
            await self._stream_ai_audio(response, self.scenario.character_gender)

        except Exception as e:
            logger.error(f"[{self.session_id}] AI response error: {e}")
            await self._send_json({"status": "error", "message": "AI processing failed"})

    async def _handle_end_game(self):
        if not self.session or not self.scenario:
            logger.error(f"[{self.session_id}] Error: _handle_end_game called with no session or scenario.")
            return

        logger.info(f"[{self.session_id}] User ended the game.")

        await self._send_json({"status": "evaluating"})

        try:
            result = await llm_service.evaluate_conversation(self.session, self.scenario)
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
            logger.error(f"[{self.session_id}] Evaluation error: {e}")
            await self._send_json({"status": "error", "message": "Game result failed"})
        finally:
            self.is_active = False

    async def run(self):
        """Main entry point for the game session."""
        if not await self._load_session_data() or not self.session or not self.scenario:
            await self.websocket.close(code=1008, reason="Invalid session")
            self.is_active = False
            return

        await self._stream_ai_audio(self.session.conversation_history[0].message, self.scenario.character_gender)

        while self.is_active:
            try:
                data = await self.websocket.receive()

                if data["type"] == "websocket.receive":
                    if "text" in data and data["text"] is not None:
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
                        await self._handle_user_speech(data["bytes"])

            except WebSocketDisconnect:
                logger.info(f"[{self.session_id}] WebSocket disconnected.")
                self.is_active = False

            except Exception as e:
                logger.error(f"[{self.session_id}] Unhandled error: {e}", exc_info=True)
                self.is_active = False
        
        # Cleanup
        if self.transcriber:
            try:
                if hasattr(self.transcriber, '_is_active') and self.transcriber._is_active:
                    # stop() is synchronous
                    self.transcriber.stop()
            except Exception as e:
                logger.error(f"[{self.session_id}] Error during cleanup: {e}")
            finally:
                self.transcriber = None

        logger.info(f"[{self.session_id}] Game session ended.")