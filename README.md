# CRUX: AI-Driven Conversation Trainer

CRUX is a full-stack, real-time audio-visual application designed for practicing difficult conversations. It uses a **FastAPI** backend to power an AI character (driven by **Google Gemini**) and a **Deepgram**-powered voice.

The **vanilla JavaScript** frontend (`testing/main.html`) provides a complete interface for generating new scenarios, connecting to a live game, and interacting with the AI. The key feature is a bi-directional audio-visual system: the client visualizes the AI's voice on one canvas and the user's microphone input on another, all in real-time.
**currenly it is not Deployed bcz of API rate issue**

## 🎥 Project Demo

Watch a full video walkthrough and demo of the project in action:

**[Watch Project Demo (Google Drive)](https://drive.google.com/file/d/1UhwQmAMHq7eH29227X7AGRJDXp3lK_-S/view?usp=sharing)**


## 🚀 What This Thing Actually Does

* **Dynamic Scenario Generation**: Users can write a simple prompt (e.g., "my boss is mad about a deadline") and the AI (`scenario_generator.py`) will create a complete character, personality, and starting dialogue.
* **Real-Time AI Dialogue**: The AI (`llm_service.py`) responds dynamically based on the conversation, its personality, and the user's tone.
* **Bi-directional Audio Streaming**: Handles simultaneous Text-to-Speech (from AI) and Speech-to-Text (from user) over a single WebSocket.
* **🔥 Angry Spam Mode**: A core mechanic where the AI (`game_session.py`) detects a "BREAK" command from the LLM, triggering a rapid-fire "spam streak" of multiple angry messages and audio clips.
* **Live Audio Visualization**: The frontend (`main.html`) uses the Web Audio API to analyze both the incoming AI audio and the outgoing user audio, rendering them to separate `<canvas>` elements.
* **Performance Evaluation**: At the end of the game, the AI evaluates the user's performance and provides a score and justification.

## 🌊 The Full-Stack Flow

This diagram shows the complete user journey from starting the app to getting a final score.

```mermaid
graph TD

%% ================= Client =================
subgraph Client [Client: testing/main.html]
    A[User Loads Page] --> B{Fetch Existing Scenarios?}
    B --> |Yes| C[GET /api/v1/scenarios]
    B --> |No| D[User Writes Prompt]
    D --> E[POST /api/v1/scenarios/generate]
    C --> F[Fill Dropdown]
    E --> F
    F --> G[User Starts Game]
    G --> H[POST /api/v1/game/start/:id]
    H --> I[Receive session_id]
    I --> J[Open WebSocket /api/v1/game/ws/:session_id]
    J --> K[Game Loop: Send Mic + Receive TTS]
    K --> L[User Hold PTT]
    L --> M[Stream Mic Audio]
    M --> K
    K --> N[User Ends Game]
    N --> O[Receive Score + Feedback]
end

%% ================= Backend =================
subgraph Backend [FastAPI Backend]
    C --> DB1[(MongoDB)]
    E --> SG[scenario_generator.py]
    SG --> LLM[Gemini LLM]
    LLM --> SG
    SG --> DB2[(MongoDB)]

    H --> GE[game.py start handler]
    GE --> DB3[(MongoDB)]
    DB3 --> GE
    GE --> WS[WebSocket Session]

    WS --> GSM[GameSessionManager]
    GSM --> STT[Deepgram STT]
    STT --> GSM
    GSM --> TTS[Deepgram TTS]
    TTS --> GSM
    GSM --> LLM
    LLM --> GSM
    GSM --> O
end

%% ================= Styles =================
classDef client fill:#c3e6ff,stroke:#1573c4,stroke-width:1.7,color:#00294d;
classDef backend fill:#ead7ff,stroke:#7b2cbf,stroke-width:1.7,color:#3a0069;
classDef service fill:#fff1cc,stroke:#ffb600,stroke-width:1.5,color:#5a4500;
classDef db fill:#d5ffd4,stroke:#28a23f,stroke-width:2,color:#003c16;
classDef decision fill:#fffbc9,stroke:#c5a000,stroke-width:2,color:#6a5800;

class A,B,C,D,E,F,G,H,I,J,K,L,M,N,O client
class SG,GE,WS,GSM backend
class LLM,TTS,STT service
class DB1,DB2,DB3 db
class B decision
```

#  The Tech Stack
## Backend (app/ directory)
**Framework**: FastAPI for async APIs and WebSockets.

**Data Models**: Pydantic (app/schemas/game_schemas.py) for all data validation.

**Database**: MongoDB (via Motor in app/db/db_service.py).

**The AI**: Google Gemini (app/services/llm_service.py) for dialogue, evaluation, and JSON-forced scenario generation.

**The Voice & Ears**: Deepgram (app/services/deepgram_service.py) for real-time LiveTranscription (STT) and aura model (TTS).

## Frontend (testing/ directory)
**Client**: Vanilla JavaScript (ES6+), HTML5, and CSS3.

**Real-Time**: Native Browser WebSocket API.

**Audio Capture**: MediaRecorder API (sending audio/webm).

**Audio Playback & Viz**: Web Audio API (AudioContext, AnalyserNode) to power the custom-drawn radial visualizers.


---
# Getting This Running
You'll Need
Python 3.10+

Node.js (for npm install, though it's not strictly required for this client)

A MongoDB instance (local or cloud).

## 1. Backend Installation
Bash

### Clone the repo
git clone [[your-repo-url](https://github.com/Harsimran-singh-7765/CRUX-Conversation-that-defines)]
cd CRUX--backend

### Set up your environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

###  Install Python dependencies
pip install -r requirements.txt

### Install Node dependencies (if any)
npm install

## 2. Your Secret Variables


.env.example

Code snippet
```bash 
GOOGLE_API_KEY = "YOUR_GEMINI_API_KEY"

DEEPGRAM_API_KEY= YOUR_DEEPGRAM_API_KEY



MONGODB_URI=mongodb+srv://username:passowrd4@db.6jg0r2p.mongodb.net/?appName=CruxClustor

```
# Get from Google AI Studio
GOOGLE_API_KEY="YOUR_GEMINI_API_KEY"

# Get from your Deepgram account
DEEPGRAM_API_KEY="YOUR_DEEPGRAM_API_KEY"

# Your MongoDB connection string
MONGODB_URI="mongodb+srv://username:passowrd4@db.6jg0r2p.mongodb.net/?appName=CruxClustor"
## 3. Fire It Up
You need two terminals.

#### Terminal 1: Run the Backend

```Bash

# Run the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
#### Terminal 2: Run the Frontend

``` Bash

# Serve the root directory (so it can find /testing/main.html)
python -m http.server 3000
Now, open your browser and go to: http://localhost:3000/testing/main.html
```
