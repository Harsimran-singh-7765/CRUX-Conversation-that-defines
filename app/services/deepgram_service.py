import logging
import random
import httpx
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Voice Models ---
MALE_VOICES = [
    "aura-2-odysseus-en", "aura-2-apollo-en", "aura-2-arcas-en", "aura-2-aries-en",
    "aura-2-atlas-en", "aura-2-draco-en", "aura-2-hermes-en", "aura-2-hyperion-en",
    "aura-2-jupiter-en", "aura-2-mars-en", "aura-2-neptune-en", "aura-2-orion-en",
    "aura-2-orpheus-en", "aura-2-pluto-en", "aura-2-saturn-en", "aura-2-zeus-en"
]

FEMALE_VOICES = [
"aura-2-phoebe-en"
]

class LiveTranscription:
    """
    Manages a live transcription connection to Deepgram (v3 SDK).
    """
    def __init__(self, deepgram_client: DeepgramClient):
        self.client = deepgram_client
        self.dg_connection = self.client.listen.live.v("1")
        self._is_active = False
        self.full_transcript = ""

    def start(self):
        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding="opus" # Correct encoding for webm
        )
        self.dg_connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript) # type: ignore
        self.dg_connection.on(LiveTranscriptionEvents.Error, self._on_error) # type: ignore
        
        try:
            if not self.dg_connection.start(options): # type: ignore
                logger.warning("[LiveTranscription] Failed to start connection.")
                return
            self._is_active = True
            self.full_transcript = "" # Reset transcript on start
            logger.info("[LiveTranscription] Connected to Deepgram for STT.")
        except Exception as e:
            logger.error(f"[LiveTranscription] Failed to connect to Deepgram: {e}")

    # --- FIX: This function is SYNCHRONOUS ---
    def send(self, audio_chunk: bytes):
        if self._is_active:
            # --- ADDED LOG ---
            logger.debug(f"[LiveTranscription] Sending {len(audio_chunk)} bytes to Deepgram STT.")
            # ---
            self.dg_connection.send(audio_chunk) # type: ignore
    # --- END FIX ---

    def _on_transcript(self, *args, **kwargs):
        result = kwargs.get("result")
        if result and result.channel and result.channel.alternatives:
            transcript = result.channel.alternatives[0].transcript
            if transcript:
                # --- ADDED LOG ---
                logger.debug(f"[LiveTranscription] Partial transcript received: '{transcript}'")
                # ---
                self.full_transcript += transcript + " "

    def _on_error(self, *args, **kwargs):
        error = kwargs.get("error")
        logger.error(f"[LiveTranscription] Deepgram Error: {error}")

    def stop(self) -> str:
        """Stops the connection and returns the final accumulated transcript."""
        if self._is_active:
            self._is_active = False
            self.dg_connection.finish() # .finish() is synchronous
            logger.info("[LiveTranscription] Connection closed.")
        
        # --- ADDED LOG ---
        logger.info(f"[LiveTranscription] Final transcript being returned: '{self.full_transcript.strip()}'")
        # ---
        return self.full_transcript.strip()

class DeepgramService:
    """
    A service to interact with Deepgram's APIs for Text-to-Speech and Speech-to-Text.
    """
    def __init__(self):
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.http_client = httpx.AsyncClient()
        self.tts_url = "https://api.deepgram.com/v1/speak"

    async def text_to_speech_stream(self, text: str, gender: str):
        if gender.lower() == 'male':
            model = random.choice(MALE_VOICES)
        else:
            model = random.choice(FEMALE_VOICES)

        logger.info(f"[DeepgramService] Requesting TTS for: '{text[:60]}...' (model: {model})")

        headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Correct params for browser-playable audio
        params = {
            "model": model,
            "container": "wav",
            "encoding": "linear16",
            "sample_rate": 24000
        }
        
        payload = {"text": text}
        
        # --- ADDED LOG ---
        logger.debug(f"[DeepgramService] TTS Request Details: URL={self.tts_url}, Model={model}, Params={params}")
        # ---

        try:
            async with self.http_client.stream("POST", self.tts_url, headers=headers, params=params, json=payload, timeout=60) as response:
                if response.is_error:
                    error_body = await response.aread()
                    logger.error(f"[DeepgramService] Error from API: {response.status_code} - {error_body.decode()}")
                    response.raise_for_status()

                logger.info(f"[DeepgramService] Success: 200. Streaming audio...")
                async for chunk in response.aiter_bytes():
                    # --- ADDED LOG ---
                    logger.debug(f"[DeepgramService] Yielding audio chunk: {len(chunk)} bytes")
                    # ---
                    yield chunk
                logger.info("[DeepgramService] Audio stream finished.")

        except httpx.RequestError as e:
            logger.error(f"[DeepgramService] HTTP Request Error: {e}")
        except Exception as e:
            logger.error(f"[DeepgramService] An unexpected error occurred: {e}")
        finally:
            logger.info(f"[DeepgramService] TTS function finished for: '{text[:60]}...'")

    def get_live_transcriber(self) -> "LiveTranscription":
        """
        Returns an instance of the asynchronous LiveTranscription manager.
        """
        return LiveTranscription(self.client)

# Singleton instance for easy access
deepgram_service = DeepgramService()