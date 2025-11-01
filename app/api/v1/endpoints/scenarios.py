import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from app.schemas.game_schemas import Scenario
from app.db import db_service
from app.services.scenario_generator import get_scenario_generator
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# === Request/Response Models ===

class GenerateScenarioRequest(BaseModel):
    """Request model for generating a new scenario."""
    description: str = Field(
        ..., 
        min_length=10, 
        max_length=500,
        description="Description of the scenario to generate"
    )

class GenerateScenarioResponse(BaseModel):
    """Response model after generating a scenario."""
    scenario: Scenario
    message: str = "Scenario generated successfully"

# === Endpoints ===

@router.get(
    "/",
    response_model=List[Scenario],
    summary="List all available scenarios"
)
async def list_all_scenarios():
    """
    Fetches all scenarios from the database (both pre-made and custom).
    Sorted by creation date (newest first).
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
    Fetches the detailed information for a single scenario by its unique string ID.
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
        raise he
    except Exception as e:
        logger.error(f"Error getting scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch scenario from database."
        )

@router.post(
    "/generate",
    response_model=GenerateScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new custom scenario using AI"
)
async def generate_custom_scenario(request: GenerateScenarioRequest):
    """
    Generates a complete scenario from a user description using Claude AI.
    The scenario is automatically saved to the database and ready to play.
    
    **Example descriptions:**
    - "My mom caught me coming home at 3 AM drunk"
    - "My boss is angry I missed an important deadline"
    - "My roommate keeps eating my food without asking"
    - "A taxi driver is taking a suspicious route late at night"
    """
    logger.info(f"POST /scenarios/generate - Description: {request.description[:50]}...")
    
    try:
        # Generate scenario using AI
        generator = get_scenario_generator()
        scenario_data = await generator.generate_scenario(request.description)
        
        # Create unique ID from title
        scenario_id = _create_scenario_id(scenario_data["title"])
        
        # Check if ID already exists
        if await db_service.db_check_scenario_exists(scenario_id):
            # Add timestamp to make it unique
            scenario_id = f"{scenario_id}_{int(datetime.utcnow().timestamp())}"
        
        # Create Scenario object with is_custom=True
        scenario = Scenario(
            id=scenario_id,
            title=f"{scenario_data['title']} (Custom)",
            character_name=scenario_data["character_name"],
            character_gender=scenario_data["character_gender"],
            personality_prompt=scenario_data["personality_prompt"],
            initial_dialogue=scenario_data["initial_dialogue"],
            is_custom=True,
            created_at=datetime.utcnow()
        )
        
        # Save to database
        await db_service.db_create_scenario(scenario)
        
        logger.info(f"Successfully created custom scenario: {scenario_id}")
        return GenerateScenarioResponse(scenario=scenario)
        
    except ValueError as ve:
        logger.error(f"Validation error generating scenario: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scenario data: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"Error generating scenario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate scenario. Please try again."
        )

@router.delete(
    "/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scenario by ID"
)
async def delete_scenario(scenario_id: str):
    """
    Deletes a scenario by its ID.
    Typically used for removing custom scenarios.
    """
    logger.info(f"DELETE /scenarios/{scenario_id} - Attempting to delete scenario")
    
    try:
        deleted = await db_service.db_delete_scenario(scenario_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario with ID '{scenario_id}' not found."
            )
        logger.info(f"Successfully deleted scenario: {scenario_id}")
        return None  # 204 No Content
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error deleting scenario {scenario_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete scenario."
        )

# === Helper Functions ===

def _create_scenario_id(title: str) -> str:
    """
    Create a URL-safe ID from a scenario title.
    Example: "The Late Night Call" -> "the_late_night_call"
    """
    # Convert to lowercase
    id_str = title.lower()
    # Remove (Custom) tag if present
    id_str = re.sub(r'\s*\(custom\)\s*', '', id_str)
    # Replace spaces and special chars with underscores
    id_str = re.sub(r'[^\w\s-]', '', id_str)
    id_str = re.sub(r'[-\s]+', '_', id_str)
    # Remove leading/trailing underscores
    id_str = id_str.strip('_')
    return id_str