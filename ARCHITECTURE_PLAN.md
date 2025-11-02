#  `ARCHITECTURE_PLAN.md` (Backend & Schemas)

# CRUX: Backend Architecture & Schemas

This document outlines the Python/FastAPI backend in `app/` and the Pydantic schemas that power it.

## 1. Core Project Structure (`app/`)

The backend is a standard FastAPI application with a clear separation of concerns.
```markdown
(base) ➜  crux_backend git:(master) ✗ tree -I venv
.
├── app
│   ├── api
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   └── __init__.cpython-313.pyc
│   │   └── v1
│   │       ├── api_router.py
│   │       ├── endpoints
│   │       │   ├── game.py
│   │       │   ├── __init__.py
│   │       │   ├── __pycache__
│   │       │   │   ├── game.cpython-313.pyc
│   │       │   │   ├── __init__.cpython-313.pyc
│   │       │   │   └── scenarios.cpython-313.pyc
│   │       │   └── scenarios.py
│   │       ├── __init__.py
│   │       └── __pycache__
│   │           ├── api_router.cpython-313.pyc
│   │           └── __init__.cpython-313.pyc
│   ├── core
│   │   ├── config.py
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       ├── config.cpython-313.pyc
│   │       └── __init__.cpython-313.pyc
│   ├── db
│   │   ├── db_service.py
│   │   ├── __init__.py
│   │   ├── mongodb_utils.py
│   │   └── __pycache__
│   │       ├── db_service.cpython-313.pyc
│   │       ├── __init__.cpython-313.pyc
│   │       └── mongodb_utils.cpython-313.pyc
│   ├── __init__.py
│   ├── main.py
│   ├── __pycache__
│   │   ├── __init__.cpython-313.pyc
│   │   └── main.cpython-313.pyc
│   ├── schemas
│   │   ├── game_schemas.py
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       ├── game_schemas.cpython-313.pyc
│   │       └── __init__.cpython-313.pyc
│   └── services
│       ├── deepgram_service.py
│       ├── game_session.py
│       ├── __init__.py
│       ├── llm_service.py
│       ├── __pycache__
│       │   ├── deepgram_service.cpython-313.pyc
│       │   ├── game_session.cpython-313.pyc
│       │   ├── __init__.cpython-313.pyc
│       │   ├── llm_service.cpython-313.pyc
│       │   └── scenario_generator.cpython-313.pyc
│       └── scenario_generator.py
├── node_modules
# many files
├── package.json
├── package-lock.json
├── requirements copy.txt
├── requirements.txt
├── scripts
│   ├── cleaning past_mistakes.py
│   └── seed_scenarios.py
├── static
│   └── audio
│       ├── 75959cdb-b5b9-4a62-8b0c-616a35ec18b4.wav
│       └── d174654d-9d5e-4d7c-8625-c4f88a3b6f5f.wav
└── testing
    ├── fixing past_mistakes.py
    ├── libs
    │   └── waviz.umd.js
    ├── list_models.py
    ├── main.html
    ├── script.js
    ├── style.css
    ├── test_gemini_model.py
    └── test.html
```
## 2. Data Schemas (`app/schemas/game_schemas.py`)

Pydantic models define all data structures.

* ### `Scenario`
    The blueprint for a conversation. This is what's stored in the DB and created by the `scenario_generator`.
    * `id: str` (Unique ID, e.g., "forgotten_birthday")
    * `title: str` (Human-readable title)
    * `character_name: str`
    * `character_gender: Literal["male", "female"]`
    * `personality_prompt: str` (The *secret* instructions for the LLM)
    * `initial_dialogue: str` (The first line the AI says)
    * `is_custom: bool` (True if user-generated)

* ### `ConversationEntry`
    A single message within a session.
    * `role: Literal["user", "ai"]`
    * `message: str`

* ### `GameSession`
    The record of a single playthrough, stored in the DB.
    * `session_id: UUID` (The primary key)
    * `user_id: str`
    * `scenario_id: str` (Links to the `Scenario`)
    * `status: Literal["active", "finished"]`
    * `conversation_history: List[ConversationEntry]`
    * `final_score: Optional[int]`
    * `final_justification: Optional[str]`

## 3. Service Layer (`app/services/`)

This is where the magic happens.

* ### `scenario_generator.py`
    * **Purpose**: Creates new `Scenario` objects from user prompts.
    * **Key Function**: `generate_scenario(description)`
    * **How**: It uses the Gemini `generate_content` function with `response_mime_type="application/json"` and a `response_schema`. This *forces* the AI to return a valid JSON object matching our Pydantic schema, which is then saved to the DB.

* ### `llm_service.py`
    * **Purpose**: Handles all in-game AI thinking.
    * **Key Function 1**: `get_ai_response(session, scenario)`
        * Takes the current history and personality prompt.
        * Returns a single string.
        * **Crucially, it's prompted to use the "BREAK" keyword** to signal the "Angry Spam Mode."
    * **Key Function 2**: `evaluate_conversation(session, scenario)`
        * Takes the *entire* transcript.
        * Returns an `EvaluationResult` Pydantic model (score, justification) by using Gemini's JSON response mode.

* ### `deepgram_service.py`
    * **Purpose**: Manages all audio I/O.
    * **Key Feature 1**: `text_to_speech_stream(text, gender)`
        * An `async generator` that calls Deepgram's TTS API.
        * It `yield`s raw audio chunks as they arrive, allowing for low-latency streaming.
    * **Key Feature 2**: `LiveTranscription` (Class)
        * A wrapper for Deepgram's live STT.
        * `start()`: Opens the connection.
        * `send(chunk)`: Sends user's mic audio.
        * `stop()`: Closes the connection and returns the final `full_transcript`.

* ### `game_session.py`
    * **Purpose**: The **State Machine** for a single WebSocket connection.
    * **How**: An instance of `GameSessionManager` is created for *each user*. It orchestrates all other services.
    * It listens for user JSON messages (`start_speaking`, `end_game`).
    * It listens for user audio `bytes` and pipes them to the `LiveTranscription` instance.
    * When a transcript is ready, it calls `llm_service`.
    * When the LLM response is ready, it calls `deepgram_service` and streams the audio back to the user.
