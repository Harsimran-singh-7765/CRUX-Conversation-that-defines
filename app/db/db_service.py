import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.mongodb_utils import get_database
from app.schemas.game_schemas import Scenario, GameSession, GameStartRequest, ConversationEntry
from uuid import UUID

logger = logging.getLogger(__name__)

# --- Collection Names ---
COLLECTION_SCENARIOS = "scenarios"
COLLECTION_SESSIONS = "game_sessions"

# === Scenario Functions ===
# (These are unchanged and fine)
async def db_create_scenario(scenario: Scenario) -> Scenario:
    db = await get_database()
    logger.info(f"Attempting to create scenario: {scenario.id}")
    await db[COLLECTION_SCENARIOS].insert_one(scenario.model_dump())
    logger.info(f"Successfully created scenario: {scenario.id}")
    return scenario

async def db_get_scenario(scenario_id: str) -> Scenario | None:
    db = await get_database()
    logger.info(f"Attempting to find scenario: {scenario_id}")
    scenario_doc = await db[COLLECTION_SCENARIOS].find_one({"id": scenario_id})
    if scenario_doc:
        logger.info(f"Found scenario: {scenario_id}")
        return Scenario(**scenario_doc)
    logger.warning(f"Could not find scenario: {scenario_id}")
    return None

async def db_list_scenarios() -> list[Scenario]:
    db = await get_database()
    logger.info("Attempting to list all scenarios")
    scenarios = []
    cursor = db[COLLECTION_SCENARIOS].find({})
    async for scenario_doc in cursor:
        scenarios.append(Scenario(**scenario_doc))
    logger.info(f"Found {len(scenarios)} scenarios")
    return scenarios


# === Game Session Functions ===

async def db_create_game_session(user_id: str, scenario: Scenario) -> GameSession:
    """
    Creates a new game session for a user and a specific scenario.
    """
    db = await get_database()
    logger.info(f"Creating new game session for user {user_id} and scenario {scenario.id}")
    
    initial_entry = ConversationEntry(
        role="ai",
        message=scenario.initial_dialogue
    )
    
    new_session = GameSession(
        user_id=user_id,
        scenario_id=scenario.id,
        conversation_history=[initial_entry]
    )
    
    # --- THIS IS THE FIX ---
    # Dump the model to a dict, but then OVERRIDE the 'session_id' field
    # with the original UUID object. This forces motor to store it
    # as the 'standard' BSON Binary type, not a string.
    session_data = new_session.model_dump()
    session_data["session_id"] = new_session.session_id 
    await db[COLLECTION_SESSIONS].insert_one(session_data)
    # --- END FIX ---
    
    logger.info(f"Successfully created game session: {new_session.session_id}")
    return new_session

async def db_get_game_session(session_id: UUID) -> GameSession | None:
    """
    Fetches an active game session by its UUID.
    """
    db = await get_database()
    
    # --- THIS IS THE FIX ---
    # We now query using the raw UUID object, not its string representation.
    # This will match the BSON Binary type in the database.
    logger.info(f"Attempting to find game session by UUID object: {session_id}")
    session_doc = await db[COLLECTION_SESSIONS].find_one({"session_id": session_id})
    # --- END FIX ---

    if session_doc:
        logger.info(f"Found game session: {session_id}")
        return GameSession(**session_doc)
    
    logger.warning(f"Could not find game session: {session_id}")
    return None

async def db_end_game_session(session_id: UUID, score: int, justification: str) -> None:
    """
    Finds a game session and updates it with the final score.
    """
    db = await get_database()
    
    # --- THIS IS THE FIX ---
    # Also query by the UUID object here.
    logger.info(f"Updating final score for session: {session_id}")
    await db[COLLECTION_SESSIONS].update_one(
        {"session_id": session_id},
        {
            "$set": {
                "status": "finished",
                "final_score": score,
                "final_justification": justification
            }
        }
    )