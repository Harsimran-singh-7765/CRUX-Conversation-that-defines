"""
Pydantic schemas for the Crux game system.
Includes scenarios, game sessions, and conversation models.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

# === Scenario Models ===

class Scenario(BaseModel):
    """
    Represents a complete game scenario with all configuration.
    """
    id: str = Field(
        ...,
        description="Unique identifier (e.g., 'drunk_driving_incident')"
    )
    title: str = Field(
        ...,
        description="Human-readable title shown in UI"
    )
    character_name: str = Field(
        default="Unknown",  # ✅ FIX: Default for backward compatibility
        description="Name of the AI character"
    )
    character_gender: Literal["male", "female"] = Field(
        default="male",  # ✅ FIX: Default for backward compatibility
        description="Gender for voice synthesis"
    )
    personality_prompt: str = Field(
        default="",  # ✅ Already fixed
        description="Full personality and behavior instructions for the AI"
    )
    initial_dialogue: str = Field(
        ...,
        description="First message the AI sends to start the conversation"
    )
    is_custom: bool = Field(
        default=False,
        description="Whether this is a user-generated custom scenario"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this scenario was created"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "forgotten_birthday",
                "title": "The Forgotten Birthday",
                "character_name": "Priya",
                "character_gender": "female",
                "personality_prompt": "You are Priya, a 22-year-old girlfriend...",
                "initial_dialogue": "So... did you remember what day it is today?",
                "is_custom": False,
                "created_at": "2025-11-01T12:00:00Z"
            }
        }


# === Conversation Models ===

class ConversationEntry(BaseModel):
    """
    A single message in the conversation history.
    """
    role: Literal["user", "ai"] = Field(
        ...,
        description="Who sent this message"
    )
    message: str = Field(
        ...,
        description="The actual text content"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this message was sent"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role": "ai",
                "message": "So... did you remember what day it is today?",
                "timestamp": "2025-11-01T12:00:00Z"
            }
        }


# === Game Session Models ===

class GameSession(BaseModel):
    """
    Represents an active game session.
    """
    session_id: UUID = Field(
        default_factory=uuid4,
        description="Unique session identifier"
    )
    user_id: str = Field(
        ...,
        description="User playing this session"
    )
    scenario_id: str = Field(
        ...,
        description="Which scenario is being played"
    )
    status: Literal["active", "finished"] = Field(
        default="active",
        description="Current session status"
    )
    conversation_history: List[ConversationEntry] = Field(
        default_factory=list,
        description="All messages exchanged in this session"
    )
    final_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Final evaluation score (0-10)"
    )
    final_justification: Optional[str] = Field(
        default=None,
        description="Explanation of the final score"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this session was created"
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="When this session ended"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user123",
                "scenario_id": "forgotten_birthday",
                "status": "active",
                "conversation_history": [],
                "final_score": None,
                "final_justification": None,
                "created_at": "2025-11-01T12:00:00Z",
                "ended_at": None
            }
        }


# === Request/Response Models ===

class GameStartRequest(BaseModel):
    """
    Request to start a new game session.
    """
    user_id: str = Field(
        ...,
        description="Unique identifier for the user"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123"
            }
        }


class GameStartResponse(BaseModel):
    """
    Response after starting a new game.
    """
    session_id: UUID = Field(
        ...,
        description="Unique session ID for WebSocket connection"
    )
    scenario: Scenario = Field(
        ...,
        description="Complete scenario information"
    )
    conversation_history: List[ConversationEntry] = Field(
        ...,
        description="Initial conversation (AI's first message)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "scenario": {
                    "id": "forgotten_birthday",
                    "title": "The Forgotten Birthday",
                    "character_name": "Priya",
                    "character_gender": "female",
                    "personality_prompt": "You are Priya...",
                    "initial_dialogue": "So... did you remember?",
                    "is_custom": False,
                    "created_at": "2025-11-01T12:00:00Z"
                },
                "conversation_history": [
                    {
                        "role": "ai",
                        "message": "So... did you remember what day it is today?",
                        "timestamp": "2025-11-01T12:00:00Z"
                    }
                ]
            }
        }


class GameEndResponse(BaseModel):
    """
    Response after ending a game with evaluation.
    """
    session_id: UUID
    score: int = Field(..., ge=0, le=10)
    justification: str

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "score": 7,
                "justification": "Good acknowledgment of feelings, but could have been more empathetic about forgetting the birthday."
            }
        }


# === WebSocket Message Models ===

class WSStatusMessage(BaseModel):
    """
    Status update messages sent over WebSocket.
    """
    status: str = Field(
        ...,
        description="Status type (ai_speaking, ai_finished_speaking, etc.)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional additional information"
    )


class WSTextMessage(BaseModel):
    """
    Text content messages sent over WebSocket.
    """
    status: Literal["user_response_text", "ai_response_text"]
    text: str


class WSSpamMessage(BaseModel):
    """
    Individual spam message in a spam streak.
    """
    status: Literal["spam_message"]
    text: str
    index: int = Field(..., description="0-based index in the spam streak")
    total: int = Field(..., description="Total number of spam messages")


class WSGameOverMessage(BaseModel):
    """
    Final game over message with score.
    """
    status: Literal["game_over"]
    score: int = Field(..., ge=0, le=10)
    justification: str


class WSErrorMessage(BaseModel):
    """
    Error message sent over WebSocket.
    """
    status: Literal["error"]
    message: str