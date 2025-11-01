import logging
import json
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
    This is the "brain" of the real-time conversation.
    """
    def __init__(self, websocket: WebSocket, session_id: UUID):
        self.websocket = websocket
        self.session_id = session_id
        self.session: GameSession | None = None
        self.scenario: Scenario | None = None
        self.transcriber = None
        self.is_active = True

    async def _load_session_data(self) -> bool:
        """Fetches the session and scenario data from the database."""
        logger.info(f"[{self.session_id}] Loading session data...")
        self.session = await db_service.db_get_game_session(self.session_id)
        if not self.session:
            logger.error(f"[{self.session_id}] Invalid session ID. Session not found.")
            return False
        
        self.scenario = await db_service.db_get_scenario(self.session.scenario_id)
        if not self.scenario:
            logger.error(f"[{self.session_id}] Scenario '{self.session.scenario_id}' not found.")
            return False
            
        logger.info(f"[{self.session_id}] Data loaded for scenario: {self.scenario.title}")
        return True

    async def _send_json(self, data: dict):
        """Helper to send JSON data over the WebSocket."""
        if self.is_active:
            await self.websocket.send_text(json.dumps(data))

    async def _stream_ai_audio(self, text: str, gender: str):
        """Streams AI-generated TTS audio to the client."""
        logger.info(f"[{self.session_id}] Streaming AI audio for text: '{text[:50]}...'")
        
        # 1. Signal that AI is about to speak
        await self._send_json({"status": "ai_speaking"})
        
        # 2. Get the TTS audio stream from Deepgram
        try:
            async for audio_chunk in deepgram_service.text_to_speech_stream(text, gender):
                if self.is_active:
                    # 3. Send the raw audio bytes to the client
                    await self.websocket.send_bytes(audio_chunk)
            
            # 4. Signal that AI has finished speaking
            await self._send_json({"status": "ai_finished_speaking"})
            logger.info(f"[{self.session_id}] Finished streaming AI audio.")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Error during TTS streaming: {e}")
            await self._send_json({"status": "error", "message": "Error generating AI audio."})

    async def _handle_user_speech(self, audio_chunk: bytes):
        """Handles incoming audio from the user via the transcriber."""
        if self.transcriber:
            await self.transcriber.send(audio_chunk)

    async def _process_user_transcript(self, user_transcript: str):
        """
        Called when the user finishes speaking.
        Gets AI response and triggers the next audio stream.
        """
        if not self.session or not self.scenario:
            return # Should not happen

        logger.info(f"[{self.session_id}] User said: '{user_transcript}'")
        
        # 1. Update conversation history
        self.session.conversation_history.append(ConversationEntry(role="user", message=user_transcript))
        # We should also save this to the DB, but we'll add that later for speed.
        
        # 2. Signal that AI is "thinking"
        await self._send_json({"status": "ai_thinking"})
        
        try:
            # 3. Get the next AI response from the LLM
            ai_response = await llm_service.get_ai_response(self.session, self.scenario)
            
            # 4. Update history with AI's response
            self.session.conversation_history.append(ConversationEntry(role="ai", message=ai_response))
            
            # 5. Stream the new AI audio
            await self._stream_ai_audio(ai_response, self.scenario.character_gender)

        except Exception as e:
            logger.error(f"[{self.session_id}] Error getting AI response: {e}")
            await self._send_json({"status": "error", "message": "Error processing AI response."})

    async def _handle_end_game(self):
        """Handles the 'end_game' request from the client."""
        if not self.session or not self.scenario:
            return

        logger.info(f"[{self.session_id}] End game requested by user.")
        await self._send_json({"status": "evaluating"})
        
        try:
            # 1. Get final evaluation
            result = await llm_service.evaluate_conversation(self.session, self.scenario)
            
            # 2. Save final score to DB
            await db_service.db_end_game_session(
                session_id=self.session.session_id,
                score=result.score,
                justification=result.justification
            )
            
            # 3. Send final score to client
            await self._send_json({
                "status": "game_over",
                "score": result.score,
                "justification": result.justification
            })
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Error during evaluation: {e}")
            await self._send_json({"status": "error", "message": "Error finalizing game."})
        finally:
            self.is_active = False

    async def run(self):
        """The main loop that manages the WebSocket connection."""
        try:
            # 1. Load data
            if not await self._load_session_data() or not self.session or not self.scenario:
                await self.websocket.close(code=1008, reason="Invalid session")
                return
            
            # 2. Start the game by sending the first AI line
            initial_line = self.session.conversation_history[0].message
            await self._stream_ai_audio(initial_line, self.scenario.character_gender)

            # 3. Main receive loop
            while self.is_active:
                data = await self.websocket.receive()
                
                if data["type"] == "websocket.receive":
                    if "text" in data:
                        # Client is sending a JSON control message
                        message = json.loads(data["text"])
                        action = message.get("action")
                        
                        if action == "start_speaking":
                            logger.info(f"[{self.session_id}] Client action: start_speaking")
                            self.transcriber = deepgram_service.get_live_transcriber()
                            await self.transcriber.start()
                            
                        elif action == "stop_speaking":
                            logger.info(f"[{self.session_id}] Client action: stop_speaking")
                            if self.transcriber:
                                transcript = await self.transcriber.stop()
                                self.transcriber = None
                                if transcript:
                                    await self._process_user_transcript(transcript)
                                else:
                                    logger.warning(f"[{self.session_id}] No transcript received.")
                                    # Send a "speak again" signal
                                    await self._send_json({"status": "ai_finished_speaking"})

                        elif action == "end_game":
                            logger.info(f"[{self.session_id}] Client action: end_game")
                            await self._handle_end_game()

                    elif "bytes" in data:
                        # Client is streaming audio data
                        if self.transcriber:
                            await self._handle_user_speech(data["bytes"])
                            
        except WebSocketDisconnect:
            logger.info(f"[{self.session_id}] WebSocket disconnected.")
            self.is_active = False
            if self.transcriber:
                await self.transcriber.stop() # Clean up
        except Exception as e:
            logger.error(f"[{self.session_id}] An unexpected error occurred: {e}")
            self.is_active = False
        finally:
            logger.info(f"[{self.session_id}] Game session manager shutting down.")