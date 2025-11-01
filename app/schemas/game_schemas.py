from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4

class Scenario(BaseModel):
    """
    Defines a pre-made scenario that a user can play.
    This is what you will "seed" into the database.
    """
    id: str = Field(..., description="A unique slug-like ID (e.g., 'drunk_driving_incident')")
    title: str = Field(..., description="The main title of the scenario")
    description: str = Field(..., description="A brief description for the user")
    character_name: str = Field(..., description="The name of the AI character (e.g., 'Officer Miller')")
    # --- ADDED THIS LINE ---
    character_gender: str = Field(..., description="The character's gender ('male' or 'female') for voice selection")
    character_prompt: str = Field(..., description="The secret, detailed prompt for the LLM that defines its personality and goal")
    initial_dialogue: str = Field(..., description="The very first line the AI will say to start the conversation")

    class Config:
        from_attributes = True

class ConversationEntry(BaseModel):
    """
    A single entry (one line) in the conversation history.
    """
    role: str # Will be 'user' or 'ai'
    message: str

class GameSession(BaseModel):
    """
    Tracks a single, active, or completed game session for a user.
    This is the main document we will work with.
    """
    session_id: UUID = Field(default_factory=uuid4, description="The unique ID for this specific game")
    user_id: str = Field(..., description="The user who is playing")
    scenario_id: str = Field(..., description="Links to the Scenario.id")
    
    conversation_history: List[ConversationEntry] = Field(default_factory=list, description="The full transcript of the conversation")
    status: str = Field(default="active", description="The current state of the game ('active' or 'finished')")
    
    final_score: Optional[int] = Field(None, description="The final score (1-10) given by the evaluator")
    final_justification: Optional[str] = Field(None, description="The AI's reasoning for the score")

    class Config:
        from_attributes = True

# Request body for creating a game session
class GameStartRequest(BaseModel):
    user_id: str