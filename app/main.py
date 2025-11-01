import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongodb_utils import connect_to_mongo, close_mongo_connection
from app.api.v1.api_router import api_router # Import our new master router

# Get the logger we configured in config.py
logger = logging.getLogger(__name__)

# THIS IS THE LINE THE ERROR IS MISSING
app = FastAPI(
    title="Crux Backend",
    description="The backend for the 'Crux' high-stakes conversation simulator.",
    version="0.1.0"
)

# We are being very explicit. We are only allowing these origins.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # <-- Keep this False
    allow_methods=["*"], 
    allow_headers=["*"], 
)

@app.on_event("startup")
async def startup_event():
    logger.info("--- Crux API is starting up... ---")
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("--- Crux API is shutting down... ---")
    await close_mongo_connection()

# Include the V1 master router
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    logger.info("GET / (root) endpoint hit")
    return {"message": "Welcome to the Crux API. Go to /docs to see the API."}