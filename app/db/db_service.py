import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.mongodb_utils import get_database
from app.schemas.game_schemas import Scenario, GameSession, GameStartRequest, ConversationEntry
from uuid import UUID
from datetime import datetime
logger = logging.getLogger(__name__)

# --- Collection Names ---
COLLECTION_SCENARIOS = "scenarios"
COLLECTION_SESSIONS = "game_sessions"

# === Scenario Functions ===

async def db_create_scenario(scenario: Scenario) -> Scenario:
    """Create a new scenario in the database."""
    db = await get_database()
    logger.info(f"Attempting to create scenario: {scenario.id}")
    await db[COLLECTION_SCENARIOS].insert_one(scenario.model_dump())
    logger.info(f"Successfully created scenario: {scenario.id}")
    return scenario

async def db_get_scenario(scenario_id: str) -> Scenario | None:
    """Get a scenario by ID."""
    db = await get_database()
    logger.info(f"Attempting to find scenario: {scenario_id}")
    scenario_doc = await db[COLLECTION_SCENARIOS].find_one({"id": scenario_id})
    if scenario_doc:
        logger.info(f"Found scenario: {scenario_id}")
        # Pydantic will automatically apply the default for what_to_do if missing
        return Scenario(**scenario_doc)
    logger.warning(f"Could not find scenario: {scenario_id}")
    return None

async def db_list_scenarios() -> list[Scenario]:
    """List all scenarios, sorted by creation date (newest first)."""
    db = await get_database()
    logger.info("Attempting to list all scenarios")
    scenarios = []
    # Sort by created_at descending to show newest first
    cursor = db[COLLECTION_SCENARIOS].find({}).sort("created_at", -1)
    async for scenario_doc in cursor:
        # Pydantic will automatically apply the default for what_to_do if missing
        scenarios.append(Scenario(**scenario_doc))
    logger.info(f"Found {len(scenarios)} scenarios")
    return scenarios

async def db_check_scenario_exists(scenario_id: str) -> bool:
    """Check if a scenario with given ID already exists."""
    db = await get_database()
    logger.info(f"Checking if scenario exists: {scenario_id}")
    count = await db[COLLECTION_SCENARIOS].count_documents({"id": scenario_id})
    exists = count > 0
    logger.info(f"Scenario {scenario_id} exists: {exists}")
    return exists

async def db_delete_scenario(scenario_id: str) -> bool:
    """Delete a scenario by ID. Returns True if deleted, False if not found."""
    db = await get_database()
    logger.info(f"Attempting to delete scenario: {scenario_id}")
    result = await db[COLLECTION_SCENARIOS].delete_one({"id": scenario_id})
    if result.deleted_count > 0:
        logger.info(f"Successfully deleted scenario: {scenario_id}")
        return True
    logger.warning(f"Could not find scenario to delete: {scenario_id}")
    return False

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
    
    # Dump the model to a dict, but override the 'session_id' field
    # with the original UUID object to store as BSON Binary
    session_data = new_session.model_dump()
    session_data["session_id"] = new_session.session_id 
    await db[COLLECTION_SESSIONS].insert_one(session_data)
    
    logger.info(f"Successfully created game session: {new_session.session_id}")
    return new_session

async def db_get_game_session(session_id: UUID) -> GameSession | None:
    """
    Fetches an active game session by its UUID.
    """
    db = await get_database()
    
    # Query using the raw UUID object to match BSON Binary type
    logger.info(f"Attempting to find game session by UUID object: {session_id}")
    session_doc = await db[COLLECTION_SESSIONS].find_one({"session_id": session_id})
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
    
    # Query by the UUID object
    logger.info(f"Updating final score for session: {session_id}")
    await db[COLLECTION_SESSIONS].update_one(
        {"session_id": session_id},
        {
            "$set": {
                "status": "finished",
                "final_score": score,
                "final_justification": justification,
                "ended_at": datetime.utcnow() # <-- Also good to update this
            }
        }
    )
    logger.info(f"Successfully updated session {session_id} with score: {score}")
