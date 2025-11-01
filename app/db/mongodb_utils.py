from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
# We will create app.core.config next
from app.core.config import settings 

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
    
    # This line gets the database name directly from your .env
    # We will make sure 'settings.MONGODB_DB' is defined in config.py
    # This assumes your MONGODB_URI already specifies the db name 'crux_db'
    # Let's adjust this to be simpler.
    return db.client.get_default_database()


async def connect_to_mongo():
    """Connects to the MongoDB database."""
    db.client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        uuidRepresentation='standard'
    )
    print("Connected to MongoDB Atlas...")

async def close_mongo_connection():
    """Closes the MongoDB database connection."""
    if db.client:
        db.client.close()
        print("Closed MongoDB connection.")