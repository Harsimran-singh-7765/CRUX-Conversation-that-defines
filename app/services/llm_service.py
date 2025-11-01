import logging
from google import genai
from google.genai import types
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
    """Initializes and returns a GenAI client (from Radio Mirchi stack)."""
    try:
        return genai.Client(api_key=settings.GOOGLE_API_KEY)
    except Exception as e:
        logger.error(f"Error configuring GenAI client: {e}")
        raise LLMServiceError(f"Error configuring GenAI client: {e}")

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

def get_ai_response(session: GameSession, scenario: Scenario) -> str:
    """
    Generates the AI character's next response (SYNCHRONOUS).
    """
    logger.info(f"Generating AI response for session: {session.session_id}")
    transcript = _format_history_for_llm(session.conversation_history)
    
    prompt = f"""
    You are a character in a high-stakes conversation.
    YOUR SECRET PROMPT: "{scenario.character_prompt}"
    CONVERSATION HISTORY:
    {transcript}
    
    You are the AI. It is your turn to speak. 
    Based *only* on your secret prompt and the history, generate your next response.
    Do not add 'AI:' or any other prefix. Just say your line.
    """
    
    try:
        model_name = "gemini-2.0-flash" # The model that worked in your test

        config = types.GenerateContentConfig(temperature=0.9)
        response = llm_client.models.generate_content(
            model=model_name,
            # --- THIS IS THE FIX ---
            # Pass the prompt string directly, as per the documentation
            contents=prompt,
            # --- END FIX ---
            config=config 
        )
        ai_message = response.text.strip()
        logger.info(f"AI Response generated: {ai_message[:50]}...")
        return ai_message
    except Exception as e:
        logger.error(f"Error during AI response generation: {e}")
        raise LLMServiceError(f"AI Response Failure: {e}")

def evaluate_conversation(session: GameSession, scenario: Scenario) -> EvaluationResult:
    """
    Evaluates the user's performance (SYNCHRONOUS).
    """
    logger.info(f"Evaluating conversation for session: {session.session_id}")
    transcript = _format_history_for_llm(session.conversation_history)
    
    prompt = f"""
    You are a conversation evaluator. Your task is to rate the user's performance.
    THE USER'S GOAL: "{scenario.description}"
    FULL CONVERSATION TRANSCRIPT:
    {transcript}
    
    INSTRUCTIONS:
    Rate the user's success from 1-10.
    Provide a one-sentence justification.
    You must return *ONLY* a valid JSON object with keys "score" (int) and "justification" (str).
    """
    
    try:
        model_name = "gemini-2.0-flash" # The model that worked in your test

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EvaluationResult,
        )
        response = llm_client.models.generate_content(
            model=model_name,
            # --- THIS IS THE FIX ---
            # Pass the prompt string directly, as per the documentation
            contents=prompt,
            # --- END FIX ---
            config=config
        )
        
        if hasattr(response, 'parsed') and isinstance(response.parsed, EvaluationResult):
            logger.info(f"Evaluation complete. Score: {response.parsed.score}")
            return response.parsed
        
        # Fallback if .parsed doesn't work
        logger.warning("LLM did not return a parsed object. Attempting manual JSON parse.")
        clean_json_str = response.text.strip().lstrip("```json").rstrip("```")
        result = EvaluationResult.model_validate_json(clean_json_str)
        logger.info(f"Evaluation complete (manual parse). Score: {result.score}")
        return result
        
    except Exception as e:
        logger.error(f"Error during conversation evaluation: {e}")
        raise LLMServiceError(f"Evaluation Failure: {e}")