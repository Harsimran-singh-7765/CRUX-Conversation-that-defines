import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.mongodb_utils import get_database  # This is an async function
from app.schemas.game_schemas import Scenario, GameSession, GameStartRequest, ConversationEntry
from uuid import UUID

logger = logging.getLogger(__name__)

# --- Collection Names ---
COLLECTION_SCENARIOS = "scenarios"
COLLECTION_SESSIONS = "game_sessions"

# === Scenario Functions ===

async def db_create_scenario(scenario: Scenario) -> Scenario:
    """
    Adds a new pre-made scenario to the database.
    This is for your seed script.
    """
    db = await get_database() # <-- FIX: Await the database connection here
    logger.info(f"Attempting to create scenario: {scenario.id}")
    await db[COLLECTION_SCENARIOS].insert_one(scenario.model_dump())
    logger.info(f"Successfully created scenario: {scenario.id}")
    return scenario

async def db_get_scenario(scenario_id: str) -> Scenario | None:
    """
    Fetches a single scenario by its unique string ID.
    """
    db = await get_database() # <-- FIX: Await the database connection here
    logger.info(f"Attempting to find scenario: {scenario_id}")
    scenario_doc = await db[COLLECTION_SCENARIOS].find_one({"id": scenario_id})
    if scenario_doc:
        logger.info(f"Found scenario: {scenario_id}")
        return Scenario(**scenario_doc)
    logger.warning(f"Could not find scenario: {scenario_id}")
    return None

async def db_list_scenarios() -> list[Scenario]:
    """
    Fetches all available scenarios from the database.
    """
    db = await get_database() # <-- FIX: Await the database connection here
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
    db = await get_database() # <-- FIX: Await the database connection here
    logger.info(f"Creating new game session for user {user_id} and scenario {scenario.id}")
    
    # Create the initial conversation entry from the scenario's first line
    initial_entry = ConversationEntry(
        role="ai",
        message=scenario.initial_dialogue
    )
    
    # Create the new session object
    new_session = GameSession(
        user_id=user_id,
        scenario_id=scenario.id,
        conversation_history=[initial_entry] # Start the history
    )
    
    # Insert into the database
    await db[COLLECTION_SESSIONS].insert_one(new_session.model_dump())
    logger.info(f"Successfully created game session: {new_session.session_id}")
    return new_session

async def db_get_game_session(session_id: UUID) -> GameSession | None:
    """
    Fetches an active game session by its UUID.
    """
    db = await get_database() # <-- FIX: Await the database connection here
    logger.info(f"Attempting to find game session: {session_id}")
    session_doc = await db[COLLECTION_SESSIONS].find_one({"session_id": session_id})
    
async def db_end_game_session(session_id: UUID, score: int, justification: str) -> None:
    """
    Finds a game session and updates it with the final score.
    """
    db = await get_database()
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