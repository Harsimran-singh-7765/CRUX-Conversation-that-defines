import os
import logging
from dotenv import load_dotenv
from google import genai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    logger.error("Error: GOOGLE_API_KEY environment variable not set.")
    exit(1)

# Initialize client
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    logger.info("GenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing GenAI client: {e}")
    exit(1)

logger.info("\n--- Fetching Available Models ---")

try:
    found_models = False
    # This loop will print the name of every model your key can see
    for model in client.models.list():
        logger.info(f"  Found Model Name: {model.name}")
        found_models = True
    
    if not found_models:
        logger.warning("  [FAILED] No models were returned from the API.")

except Exception as e:
    logger.error(f"  [ERROR] Failed to list models: {e}")

logger.info("---------------------------------")