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
    
    # Count how many times user has been dismissive/rude
    user_messages = [e.message.lower() for e in session.conversation_history if e.role == "user"]
    anger_triggers = ["fuck", "don't care", "break up", "grow up", "stop", "child", "whatever", "shut up"]
    anger_level = sum(1 for msg in user_messages for trigger in anger_triggers if trigger in msg)
    
    # ✅ CHANGE: character_prompt → personality_prompt
    prompt = f"""
    You are a character in a high-stakes conversation.
    YOUR SECRET PROMPT: "{scenario.personality_prompt}"
    CONVERSATION HISTORY:
    {transcript}
    
    CURRENT ANGER LEVEL: {anger_level}/5
    
    IMPORTANT INSTRUCTIONS:
    1. You are the AI. It is your turn to speak.
    2. Based on your secret prompt and the history, generate your next response.
    3. Do not add 'AI:' or any other prefix. Just say your line.
    
    4. **ANGRY SPAM MECHANIC:**
       - If the user is being extremely dismissive, rude, or hurtful (especially with profanity or breakup threats)
       - AND your anger level is 2 or higher
       - You can use "BREAK" to split your response into rapid-fire emotional bursts
       - Each segment between BREAK will be delivered as a separate angry message
       - Use 2-5 segments maximum
       - Each segment should be SHORT (5-15 words) and emotionally charged
       
    EXAMPLE OF ANGRY SPAM MODE:
    "Are you SERIOUS right now? BREAK After everything I've done for you? BREAK You forgot MY BIRTHDAY! BREAK And now you're telling ME to grow up? BREAK Unbelievable!"
    
    NORMAL RESPONSE (if not very angry):
    "That really hurts. I can't believe you forgot my birthday..."
    
    Current situation: The user has triggered {anger_level} anger points. Respond accordingly.
    """
    
    try:
        model_name = "gemini-2.0-flash"

        config = types.GenerateContentConfig(temperature=0.9)
        response = llm_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config 
        )
        ai_message = response.text.strip()
        
        # Log if spam mode is triggered
        if "BREAK" in ai_message:
            segments = [s.strip() for s in ai_message.split("BREAK") if s.strip()]
            logger.info(f"🔥 ANGRY SPAM MODE TRIGGERED! {len(segments)} segments")
            logger.info(f"Preview: {segments[0][:30]}...")
        else:
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
    
    # ✅ CHANGE: scenario.description removed (doesn't exist in new schema)
    # Use scenario.title and personality_prompt instead
    prompt = f"""
    You are a conversation evaluator. Your task is to rate the user's performance.
    SCENARIO: "{scenario.title}"
    CHARACTER CONTEXT: "{scenario.personality_prompt[:200]}..."
    
    FULL CONVERSATION TRANSCRIPT:
    {transcript}
    
    INSTRUCTIONS:
    Rate how well the user handled this difficult conversation from 1-10.
    Consider: empathy, de-escalation, acknowledgment, resolution attempts.
    Provide a one-sentence justification.
    You must return *ONLY* a valid JSON object with keys "score" (int) and "justification" (str).
    """
    
    try:
        model_name = "gemini-2.0-flash"

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EvaluationResult,
        )
        response = llm_client.models.generate_content(
            model=model_name,
            contents=prompt,
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