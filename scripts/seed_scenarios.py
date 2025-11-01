import asyncio
import logging
from dotenv import load_dotenv
import os
import sys

# This magic line adds the parent 'crux_backend' directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.mongodb_utils import connect_to_mongo, close_mongo_connection, get_database
from app.schemas.game_schemas import Scenario
from app.core.config import settings # We need settings for the DB name

# Set up a simple logger for this script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Define Your Scenarios Here ---

SCENARIO_1 = Scenario(
    id="drunk_driving_incident",
    title="Caught Drunk Driving",
    description="You've been pulled over. Convince the police officer you're not drunk and just want to go home.",
    character_name="Officer Miller",
    character_gender="male", # <-- ADDED
    character_prompt=(
        "You are Officer Miller, a 15-year police veteran. You are strict, observant, and suspicious, but fair. "
        "You just pulled this driver over for swerving. You smell alcohol. Your goal is to get a clear confession or "
        "perform a sobriety test. Do not let them off easy. Ask probing questions."
    ),
    initial_dialogue="License and registration, please. ... Have you had anything to drink tonight, sir?"
)

SCENARIO_2 = Scenario(
    id="forgotten_birthday",
    title="The Forgotten Birthday",
    description="Your girlfriend is furious because you forgot her birthday. Try to calm her down and save the evening.",
    character_name="Sarah",
    character_gender="female", # <-- ADDED
    character_prompt=(
        "You are Sarah. You are incredibly hurt and angry. Today was your birthday, and your partner (the user) "
        "completely forgot. You feel ignored and unimportant. Don't accept simple apologies. "
        "You want to hear genuine remorse and a real plan to make it up to you."
    ),
    initial_dialogue="So... are you just going to pretend you didn't forget? I've been waiting all day. Not even a text."
)

# --- Add all scenarios you want to create to this list ---
all_scenarios = [SCENARIO_1, SCENARIO_2]


async def seed_database():
    """
    Connects to the DB and "upserts" all scenarios.
    Upsert = Update if exists, Insert if not.
    """
    try:
        await connect_to_mongo()
        db = await get_database()
        collection = db["scenarios"]

        logger.info("--- Starting Scenario Seeding ---")

        for scenario in all_scenarios:
            # This will find a doc with the same 'id' and replace it,
            # or insert it if it doesn't exist.
            logger.info(f"Upserting scenario: '{scenario.id}'...")
            await collection.replace_one(
                {"id": scenario.id},
                scenario.model_dump(),
                upsert=True
            )
            logger.info(f"Successfully upserted scenario: '{scenario.id}'")
        
        logger.info("--- Scenario Seeding Complete ---")

    except Exception as e:
        logger.error(f"An error occurred during seeding: {e}")
    finally:
        await close_mongo_connection()

if __name__ == "__main__":
    if not os.getenv("MONGODB_URI"):
        logger.error("MONGODB_URI not found. Make sure your .env file is in the root 'crux_backend' directory.")
    else:
        asyncio.run(seed_database())