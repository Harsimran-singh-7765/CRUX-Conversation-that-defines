import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Loads all environment variables from the .env file.
    Pydantic-Settings handles all the validation automatically.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    MONGODB_URI: str
    MONGODB_DB: str = "crux_db" # <-- ADD THIS LINE

    # API Keys
    GOOGLE_API_KEY: str
    DEEPGRAM_API_KEY: str
    
    def __init__(self, **values):
        super().__init__(**values)
        logger.info("Environment variables loaded successfully.")
        if not self.MONGODB_URI:
            logger.error("MONGODB_URI is not set!")
        # We can also add a check for the DB name
        if not self.MONGODB_DB:
            logger.error("MONGODB_DB is not set!")
        if not self.GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY is not set!")
        if not self.DEEPGRAM_API_KEY:
            logger.error("DEEPGRAM_API_KEY is not set!")


# Create a single, importable settings instance
settings = Settings()