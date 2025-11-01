import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
# Environment variable se URI load karein
# Make sure your MONGODB_URI is set in your environment or .env file
MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable not set. Please set it to your MongoDB Atlas connection string.")

# --- Update Settings ---
DB_NAME = "crux_db"
COLLECTION_NAME = "scenarios"
DEFAULT_PROMPT = "You are a character in a conversation scenario."

def update_scenarios_with_default_prompt():
    """
    Connects to MongoDB and updates documents where 'personality_prompt' is missing.
    """
    client = None
    try:
        # 1. MongoDB se connect karein
        print(f"Connecting to MongoDB Atlas...")
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # 2. Query aur Update operation define karein
        query = {
            "personality_prompt": {"$exists": False}
        }
        
        update_operation = {
            "$set": {
                "personality_prompt": DEFAULT_PROMPT,
                "is_custom": False,
                "created_at": datetime.now() # Current timestamp set karein
            }
        }
        
        # 3. UpdateMany operation execute karein
        print(f"Searching for documents in '{DB_NAME}.{COLLECTION_NAME}' where 'personality_prompt' is missing...")
        
        result = collection.update_many(query, update_operation)

        # 4. Result print karein
        print("\n--- Update Summary ---")
        print(f"Matched documents (जिनमें personality_prompt missing था): {result.matched_count}")
        print(f"Modified documents (जिन्हें update किया गया): {result.modified_count}")
        
        if result.modified_count > 0:
            print("Update complete. Missing personality_prompt fields have been set to default.")
        else:
            print("No documents were found needing an update.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please check your MONGODB_URI and network connection.")
    finally:
        if client:
            client.close()
            print("Connection closed.")

if __name__ == "__main__":
    update_scenarios_with_default_prompt()