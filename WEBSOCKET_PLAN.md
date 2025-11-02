# CRUX: WebSocket & Real-Time Flow

This plan details the complex, bi-directional flow of data over the WebSocket (`/api/v1/game/ws/{session_id}`) and the logic for the "Angry Spam Mode."

## 1. Core Components

* **`game.py` (The Endpoint)**: Accepts the WebSocket connection and hands it off to a manager.
* **`game_session.py` (The State Manager)**: A `GameSessionManager` object is created *per connection*. It holds the state (e.g., `self.transcriber`) and orchestrates the entire flow.
* **`script.js` (The Client)**: Manages the `WebSocket` object, user's mic (`MediaRecorder`), and audio playback/visualization (`Web Audio API`).
* **`deepgram_service.py` (The Ears/Voice)**: Provides the `LiveTranscription` class and the `text_to_speech_stream` generator.

## 2. WebSocket Lifecycle & Game Flow

The entire process is managed by the `GameSessionManager.run()` method.

### Step 1: Connection & Initialization
1.  Client connects to `WS /api/v1/game/ws/{session_id}`.
2.  `game.py` accepts the connection and creates a `GameSessionManager` instance.
3.  The manager's `run()` method starts.
4.  `_load_session_data()`: The manager fetches the `GameSession` and `Scenario` from MongoDB.
5.  `_stream_ai_audio()`: The *first* message (`initial_dialogue`) is immediately streamed to the user (see Step 3).

### Step 2: User-to-AI (STT / Mic Input)
This flow is triggered by the user holding **Push-to-Talk**.

1.  **Client (`script.js`)**: User presses button.
    * Sends JSON: `{"action": "start_speaking"}`.
    * `MediaRecorder` starts, capturing `audio/webm` chunks.
    * For each chunk, `socket.send(audioChunk)` sends raw `bytes`.
2.  **Backend (`game_session.py`)**:
    * Receives `start_speaking` JSON, calls `_start_stt()`, which creates a `self.transcriber` instance.
    * Receives audio `bytes`, calls `_handle_user_speech()`, which calls `self.transcriber.send(chunk)`.
3.  **Client (`script.js`)**: User releases button.
    * `MediaRecorder` stops.
    * Sends JSON: `{"action": "stop_speaking"}`.
4.  **Backend (`game_session.py`)**:
    * Receives `stop_speaking` JSON, calls `_stop_stt_and_process_transcript()`.
    * This calls `self.transcriber.stop()`, which returns the final `transcript`.
    * `_process_user_transcript()` is called. This sends the `transcript` to `llm_service.get_ai_response()`.
    * The LLM response (e.g., "You forgot! BREAK I can't believe you!") triggers **Step 3**.

### Step 3: AI-to-User (TTS / Audio Output)
This is the most complex flow, handled by `_stream_ai_audio()`. It has two paths:

#### Path A: Normal Response (No "BREAK")
1.  **Backend**: `_stream_ai_audio()` receives text (e.g., "I'm just really disappointed.").
2.  **Backend**: Sends `{"status": "ai_speaking"}` JSON.
3.  **Backend**: Calls `deepgram_service.text_to_speech_stream()` and `await`s chunks.
4.  **Backend**: For each chunk: `await websocket.send_bytes(chunk)`.
5.  **Client**: `socket.onmessage` receives audio `bytes`, pushes them to `audioQueue`.
6.  **Backend**: After loop: Sends `{"status": "ai_finished_speaking"}` JSON.
7.  **Client**: Receives `ai_finished_speaking`, calls `playFullAudio()` to play the queued audio.
8.  **Client**: `audioPlayer.onplay` triggers `initAudioContext()`, which feeds the audio into `analyser` for the **Left Visualizer**.

#### Path B: 🔥 Angry Spam Mode (Contains "BREAK")
This is the special mechanic.

1.  **Backend**: `_stream_ai_audio()` receives text (e.g., "You forgot! BREAK I'm so mad! BREAK Unbelievable!").
2.  **Backend**: `_split_angry_response()` splits this into `["You forgot!", "I'm so mad!", "Unbelievable!"]`.
3.  **Backend**: `_stream_angry_spam()` is called.
4.  **Backend**: Sends `{"status": "angry_spam_streak"}` JSON.
5.  **Backend**: **(Key Step)** Generates audio for *all 3 messages in parallel* using `asyncio.gather()`. This results in `[audio1_bytes, audio2_bytes, audio3_bytes]`.
6.  **Backend**: Loops through the (message, audio) pairs:
    * Sends `{"status": "spam_message", "text": "You forgot!", "index": 0, "total": 3}`.
    * Sends `audio1_bytes`.
    * Sends `{"status": "spam_message", "text": "I'm so mad!", "index": 1, "total": 3}`.
    * Sends `audio2_bytes`... (and so on).
7.  **Client**: `handleJsonMessage` sees `angry_spam_streak` and sets `isSpamMode = true`.
8.  **Client**: `handleJsonMessage` sees `spam_message`, adds text to `spamQueue`.
9.  **Client**: `handleAudioChunk` sees `isSpamMode`, adds audio `bytes` to the corresponding entry in `spamQueue`.
10. **Backend**: After loop: Sends `{"status": "spam_streak_complete"}` JSON.
11. **Client**: Receives `spam_streak_complete`, calls `playSpamStreak()`, which plays each message and its audio in sequence.

## 4. Dual Visualization (Client-Side)

The `testing/main.html` file implements two visualizers.

* `drawVisualizers()`: A `requestAnimationFrame` loop.
* **Left Canvas (AI)**: Reads from `analyser`, which is connected to the `<audio id="audioPlayer">` element. This visualizes what the AI is saying.
* **Right Canvas (User)**: Reads from `micAnalyser`, which is connected to the `MediaStream` from `navigator.mediaDevices.getUserMedia()`. This visualizes the user's live mic input.