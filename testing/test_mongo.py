import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from uuid import uuid4
import os
import sys
import pprint

# --- Load environment variables ---
load_dotenv()

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.getenv("DB_NAME") or "crux_db"
COLLECTION_SCENARIOS = "scenarios"
COLLECTION_SESSIONS = "game_sessions"

# --- Utility Pretty Printer ---
pp = pprint.PrettyPrinter(indent=2)


async def main():
    """
    Tests MongoDB connection, inserts a mock scenario and session,
    retrieves them using UUID (as your backend does), and cleans up.
    """

    print("🚀 Starting CRUX MongoDB test...")
    print(f"🔗 Using URI: {MONGO_URI}")
    print(f"🗄️ Database: {DB_NAME}")

    try:
        # --- Connect to MongoDB ---
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]

        # --- Step 1: Ping ---
        print("📡 Pinging MongoDB server...")
        await db.command("ping")
        print("✅ Connection successful!\n")

        # --- Step 2: Insert mock scenario ---
        scenario_id = str(uuid4())
        scenario_doc = {
            "id": scenario_id,
            "title": "Test Scenario",
            "description": "This is a sample scenario for MongoDB testing.",
            "initial_dialogue": "Welcome to the test simulation!"
        }

        print("🧩 Inserting test scenario...")
        await db[COLLECTION_SCENARIOS].insert_one(scenario_doc)
        print(f"✅ Inserted scenario: {scenario_id}")

        # --- Step 3: Retrieve scenario ---
        print("\n🔍 Fetching inserted scenario...")
        found_scenario = await db[COLLECTION_SCENARIOS].find_one({"id": scenario_id})
        if found_scenario:
            print("📄 Scenario retrieved:")
            pp.pprint(found_scenario)
        else:
            print("❌ Scenario not found!")

        # --- Step 4: Create a fake game session using UUID ---
        session_id = uuid4()
        game_session = {
            "session_id": session_id,  # Stored as raw UUID (not string)
            "user_id": "user_123",
            "scenario_id": scenario_id,
            "conversation_history": [
                {"role": "ai", "message": "Welcome to the test session!"}
            ],
            "status": "active",
            "final_score": None,
            "final_justification": None,
        }

        print("\n🎮 Inserting test game session...")
        await db[COLLECTION_SESSIONS].insert_one(game_session)
        print(f"✅ Created game session: {session_id}")

        # --- Step 5: Fetch game session by UUID (important test!) ---
        print("\n🔍 Fetching inserted session by UUID...")
        found_session = await db[COLLECTION_SESSIONS].find_one({"session_id": session_id})
        if found_session:
            print("📄 Game session retrieved:")
            pp.pprint(found_session)
        else:
            print("❌ Game session not found! (UUID mismatch issue)")

        # --- Step 6: Clean up (optional) ---
        print("\n🧹 Cleaning up test data...")
        await db[COLLECTION_SCENARIOS].delete_one({"id": scenario_id})
        await db[COLLECTION_SESSIONS].delete_one({"session_id": session_id})
        print("✅ Cleanup complete!")

    except Exception as e:
        print("❌ Error during MongoDB test:")
        print(e)
        sys.exit(1)

    finally:
        client.close()
        print("\n🔒 MongoDB connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
