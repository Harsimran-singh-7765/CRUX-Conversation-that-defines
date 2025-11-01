from fastapi import APIRouter
from app.api.v1.endpoints import scenarios, game

# This router combines all your v1 endpoints
api_router = APIRouter()

# We will build these files next, but we can include them now
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"])
api_router.include_router(game.router, prefix="/game", tags=["Game"])