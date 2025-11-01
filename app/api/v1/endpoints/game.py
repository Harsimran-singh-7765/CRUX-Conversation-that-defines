import logging
from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from uuid import UUID
from app.schemas.game_schemas import GameSession, GameStartRequest
from app.db import db_service
from app.services.game_session import GameSessionManager # <-- IMPORT THE BRAIN

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/start/{scenario_id}",
    response_model=GameSession,
    summary="Start a new game session"
)
async def start_game(scenario_id: str, request_body: GameStartRequest):
    """
    Starts a new game session for a given user and scenario.
    """
    logger.info(f"POST /game/start/{scenario_id} for user {request_body.user_id}")
    
    try:
        scenario = await db_service.db_get_scenario(scenario_id)
        if not scenario:
            logger.warning(f"Scenario not found: {scenario_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario with ID '{scenario_id}' not found."
            )
        
        logger.info(f"Found scenario. Creating new session...")
        new_session = await db_service.db_create_game_session(
            user_id=request_body.user_id,
            scenario=scenario
        )
        return new_session

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error starting game session for {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create new game session."
        )

# --- NEW WEBSOCKET ENDPOINT ---

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: UUID):
    """
    The main WebSocket endpoint for a live game session.
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for session: {session_id}")
    
    # Create the manager that will handle this specific game
    manager = GameSessionManager(websocket, session_id)
    
    try:
        # Run the main game loop
        await manager.run()
    except Exception as e:
        logger.error(f"Error in WebSocket manager for {session_id}: {e}")
    finally:
        logger.info(f"Closing WebSocket for session: {session_id}")
        if manager.is_active:
            await websocket.close(code=1000)