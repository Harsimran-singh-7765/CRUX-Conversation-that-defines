import logging
from google import genai
from pydantic import BaseModel, Field
from app.core.config import settings
from app.schemas.game_schemas import GameSession, Scenario, ConversationEntry

logger = logging.getLogger(__name__)

class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass

class EvaluationResult(BaseModel):
    """Pydantic model for the evaluator's JSON response."""
    score: int = Field(..., description="The final score from 1-10.")
    justification: str = Field(..., description="The AI's one-sentence justification for the score.")

def _get_genai_client():
    """Initializes and returns a GenAI client."""
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        logger.error(f"Error configuring GenAI client: {e}")
        raise LLMServiceError(f"Error configuring GenAI client: {e}")

# We create one client for the whole service
llm_client = _get_genai_client()

def _format_history_for_llm(history: list[ConversationEntry]) -> str:
    """Converts our Pydantic history into a simple text-based transcript."""
    transcript = ""
    for entry in history:
        if entry.role == "ai":
            transcript += f"AI: {entry.message}\n"
        elif entry.role == "user":
            transcript += f"User: {entry.message}\n"
    return transcript.strip()

async def get_ai_response(session: GameSession, scenario: Scenario) -> str:
    """
    Generates the AI character's next response based on the conversation history.
    """
    logger.info(f"Generating AI response for session: {session.session_id}")
    
    # 1. Format the conversation history
    transcript = _format_history_for_llm(session.conversation_history)
    
    # 2. Create the prompt
    prompt = f"""
    You are a character in a high-stakes conversation.
    
    YOUR SECRET PROMPT:
    "{scenario.character_prompt}"
    
    CONVERSATION HISTORY:
    {transcript}
    
    You are the AI. It is your turn to speak. 
    Based *only* on your secret prompt and the history, generate your next response.
    Do not add 'AI:' or any other prefix. Just say your line.
    """
    
    try:
        # 3. Call the Gemini API
        response = await llm_client.generate_content_async(
            [prompt],
            generation_config={"temperature": 0.9} # Make it a bit creative
        )
        
        ai_message = response.text.strip()
        logger.info(f"AI Response generated: {ai_message[:50]}...")
        return ai_message
        
    except Exception as e:
        logger.error(f"Error during AI response generation: {e}")
        raise LLMServiceError(f"Error generating AI response: {e}")

async def evaluate_conversation(session: GameSession, scenario: Scenario) -> EvaluationResult:
    """
    Evaluates the user's performance for the entire conversation.
    """
    logger.info(f"Evaluating conversation for session: {session.session_id}")
    
    transcript = _format_history_for_llm(session.conversation_history)
    
    # 1. Create the evaluator prompt
    prompt = f"""
    You are a conversation evaluator. Your task is to rate the user's performance.
    
    THE USER'S GOAL:
    "{scenario.description}"
    
    FULL CONVERSATION TRANSCRIPT:
    {transcript}
    
    INSTRUCTIONS:
    Based on the user's goal and the transcript, rate the user's success on a scale of 1 to 10.
    Provide a concise, one-sentence justification for the score.
    You must return *ONLY* a valid JSON object with the keys "score" (int) and "justification" (str).
    """
    
    try:
        # 2. Call the Gemini API with JSON mode
        response = await llm_client.generate_content_async(
            [prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        
        # 3. Parse and validate the response
        result = EvaluationResult.model_validate_json(response.text)
        logger.info(f"Evaluation complete. Score: {result.score}")
        return result
        
    except Exception as e:
        logger.error(f"Error during conversation evaluation: {e}")
        raise LLMServiceError(f"Error evaluating conversation: {e}")