from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings # This settings object now has MONGODB_DB

class DataBase:
    client: AsyncIOMotorClient | None = None

db = DataBase()

async def get_database() -> AsyncIOMotorDatabase:
    """
    Returns the application's database instance.
    Raises an exception if the client is not initialized.
    """
    if db.client is None:
        raise Exception("Database client not initialized. Ensure `connect_to_mongo` is called on application startup.")
    
    # --- THIS IS THE FIX ---
    # Instead of relying on a "default", we explicitly get the database
    # by its name from our settings. This is far more reliable.
    return db.client[settings.MONGODB_DB]


async def connect_to_mongo():
    """Connects to the MongoDB database."""
    db.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        uuidRepresentation='standard'
    )
    print(f"Connected to MongoDB Atlas... (Database: {settings.MONGODB_DB})") # Added a log

async def close_mongo_connection():
    """Closes the MongoDB database connection."""
    if db.client:
        db.client.close()
        print("Closed MongoDB connection.")