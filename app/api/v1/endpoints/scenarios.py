import logging
from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.game_schemas import Scenario
from app.db import db_service # Import our new database functions

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/",
    response_model=List[Scenario],
    summary="List all available scenarios"
)
async def list_all_scenarios():
    """
    Fetches all pre-made scenarios from the database.
    This is used to populate the "lobby" for the user to choose from.
    """
    logger.info("GET /scenarios/ - Attempting to list all scenarios")
    try:
        scenarios = await db_service.db_list_scenarios()
        return scenarios
    except Exception as e:
        logger.error(f"Error listing scenarios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch scenarios from database."
        )

@router.get(
    "/{scenario_id}",
    response_model=Scenario,
    summary="Get a single scenario by its ID"
)
async def get_scenario_by_id(scenario_id: str):
    """
    Fetches the detailed information for a single scenario by its unique string ID
    (e.g., "drunk_driving_incident").
    """
    logger.info(f"GET /scenarios/{scenario_id} - Attempting to get scenario")
    try:
        scenario = await db_service.db_get_scenario(scenario_id)
        if not scenario:
            logger.warning(f"Scenario not found: {scenario_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario with ID '{scenario_id}' not found."
            )
        return scenario
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error getting scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch scenario from database."
        )