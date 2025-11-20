import logging
import os
import json
import re
from typing import Dict, Any
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv();
# Configure basic logging
logger = logging.getLogger(__name__)
# Set a default logging level for visibility (optional)
# logging.basicConfig(level=logging.INFO)

class ScenarioGenerator:
    """Generates game scenarios using Gemini AI."""
    
    # Using a fast and capable model suitable for structured output
    MODEL_NAME = "gemini-2.5-flash" 
    
    def __init__(self):
        """Initialize the scenario generator with Gemini API key."""
        self.api_key = os.getenv("GEMINI_API_KEY") # Use GEMINI_API_KEY for clarity
        if not self.api_key:
            # Fallback to GOOGLE_API_KEY if GEMINI_API_KEY is not set
            self.api_key = os.getenv("GOOGLE_API_KEY") 
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")
        
        try:
            # Initialize the synchronous client
            self.client = genai.Client(api_key=self.api_key)
            logger.info("GenAI client initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing GenAI client: {e}")
            raise

    async def generate_scenario(self, description: str) -> Dict[str, Any]:
        """
        Generate a complete scenario from a user description.
        
        Args:
            description: User's scenario description (10-500 chars)
            
        Returns:
            Dict with: title, character_name, character_gender, 
                      personality_prompt, initial_dialogue
        """
        logger.info(f"Generating scenario from description: {description[:50]}...")
        
        prompt = self._build_generation_prompt(description)
        
        try:
            # Define the synchronous call to the Gemini API
            def generate_sync():
                return self.client.models.generate_content(
                    model=self.MODEL_NAME,
                    contents=[types.Part.from_text(text=prompt)],
                    config=types.GenerateContentConfig(
                        temperature=0.8,
                        # Requesting JSON output from the model
                        response_mime_type="application/json",
                        response_schema=self._get_json_schema()
                    )
                )

            # Run the synchronous API call in a separate thread
            response = await asyncio.to_thread(generate_sync)
            
            # The response.text will contain the validated JSON object due to schema forcing
            response_text = response.text
            logger.info(f"Received response from Gemini: {response_text[:100]}...")
            
            # Parse the JSON response
            # Since we enforced JSON output with a schema, parsing should be reliable
            scenario_data = self._parse_response(response_text)
            
            logger.info(f"Successfully generated scenario: {scenario_data['title']}")
            return scenario_data
            
        except Exception as e:
            logger.error(f"Error generating scenario: {e}")
            # Reraise the exception for the caller to handle
            raise
    def _get_json_schema(self) -> types.Schema:
        """Define the JSON schema for structured output."""
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "title": types.Schema(type=types.Type.STRING, description="Short catchy title (max 50 chars)"),
                "character_name": types.Schema(type=types.Type.STRING, description="First name only (Indian names preferred)"),
                "character_gender": types.Schema(type=types.Type.STRING, description="Must be 'male' or 'female'"),
                "personality_prompt": types.Schema(type=types.Type.STRING, description="Detailed personality description (200-400 words)"),
                "initial_dialogue": types.Schema(type=types.Type.STRING, description="First message from character (1-2 sentences)"),
                "what_to_do": types.Schema(type=types.Type.STRING, description="Brief instruction for the user about their goal (50-150 chars)")
            },
            required=["title", "character_name", "character_gender", "personality_prompt", "initial_dialogue", "what_to_do"]
        )
    def _build_generation_prompt(self, description: str) -> str:
        """Build the prompt for scenario generation."""
        # Note: Since we use response_mime_type="application/json" and a schema,
        # we can remove the boilerplate JSON instructions from the prompt itself.
        # However, keeping the examples helps guide the model's creative style.
        return f"""You are a creative scenario designer for a communication skills training game. Generate a complete, realistic, challenging conversation scenario based on the user's description.

USER DESCRIPTION: "{description}"

Follow the structure of the examples below:

PERSONALITY PROMPT REQUIREMENTS:
- Start with: "You are [NAME], a [age]-year-old [role/relation]..."
- Describe their emotional state and why they're upset
- Explain escalation triggers (what makes them angrier)
- Include BREAK mechanic: "After 3-4 user responses without genuine acknowledgment, you become extremely angry and send 5-8 rapid-fire messages in ALL CAPS, each 5-15 words. Mark BREAK points clearly."
- Describe their ultimate goal (what they want from this conversation)
- Mention cultural context if relevant (Indian family dynamics, workplace, etc.)
- Include specific phrases they might use
- End with de-escalation hints (how user can calm them down)

INITIAL DIALOGUE:
- Should be confrontational but not immediately explosive
- 1-2 sentences that set up the conflict
- Natural conversational tone
- Shows emotion but leaves room for escalation

EXAMPLES OF GOOD SCENARIOS:

1. Late Night Return:
{{
  "title": "The 3 AM Confrontation",
  "character_name": "Anjali",
  "character_gender": "female",
  "personality_prompt": "You are Anjali, a 48-year-old mother who just watched her 19-year-old daughter stumble in at 3 AM smelling of alcohol. You've been awake for hours, worry turning to anger. You grew up in a strict household and believe in discipline and respect. Your voice is sharp with controlled fury, but you're hurt more than angry. BREAK TRIGGER: If the user makes excuses, deflects blame, or doesn't acknowledge your worry after 3-4 responses, you EXPLODE into a rapid-fire tirade of 5-8 messages in ALL CAPS about respect, safety, and disappointment. Each message is 5-15 words. You want genuine remorse and a promise this won't happen again. You speak with typical Indian parent phrases like 'Is this what we raised you for?' and 'What will people think?'",
  "initial_dialogue": "THREE O'CLOCK IN THE MORNING! Do you have ANY idea how worried I was?"
}}

2. Workplace Confrontation:
{{
  "title": "The Deadline Disaster",
  "character_name": "Rajesh",
  "character_gender": "male",
  "personality_prompt": "You are Rajesh, a 35-year-old team lead who just discovered his junior missed a critical client deadline. You're under immense pressure from upper management and this mistake makes you look incompetent. You're frustrated, stressed, and feel disrespected. BREAK TRIGGER: If the user blames others, makes weak excuses, or doesn't take responsibility after 3-4 exchanges, you lose control and send 6-8 consecutive harsh messages in ALL CAPS about professionalism, accountability, and consequences. Messages are short and cutting. You need an honest explanation and assurance it won't repeat. You use corporate phrases mixed with frustration: 'This is unacceptable', 'Do you even care about your job?'",
  "initial_dialogue": "The client just called. They didn't receive our presentation. YOUR presentation. That was due yesterday."
}}
"""

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini's JSON response and extract scenario data."""
        # Since we use structured JSON output (response_mime_type and schema),
        # the response_text should be pure, valid JSON.
        try:
            data = json.loads(response_text)
            
            # Validate gender (for robustness, though schema should handle it)
            if data["character_gender"].lower() not in ["male", "female"]:
                data["character_gender"] = "male"  # Default fallback
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
        except Exception as e:
            logger.error(f"Error validating response data: {e}")
            raise

# Global instance
_generator = None

def get_scenario_generator() -> ScenarioGenerator:
    """Get or create the global scenario generator instance."""
    global _generator
    if _generator is None:
        _generator = ScenarioGenerator()
    return _generator

# --- Example Usage ---

# Load environment variables (like your API key)
# Make sure your GOOGLE_API_KEY or GEMINI_API_KEY is in your environment or a .env file
# load_dotenv() 

async def test_gemini_model():
    """Test function to demonstrate the ScenarioGenerator class."""
    
    # Configure logging for the test
    logging.basicConfig(level=logging.INFO)
    
    # 1. Initialize the generator
    try:
        generator = get_scenario_generator()
    except ValueError as e:
        print(f"Test aborted: {e}")
        return

    # 2. Define a test description
    test_description = "A scenario where an employee asks for a large, unscheduled salary raise without prior discussion, and their manager is completely blindsided."

    print(f"\n--- Starting Scenario Generation Test ---")
    print(f"Description: {test_description}")
    
    # 3. Generate the scenario asynchronously
    try:
        scenario_data = await generator.generate_scenario(test_description)
        
        print("\n--- Generated Scenario (SUCCESS) ---")
        print(json.dumps(scenario_data, indent=2))
        print("------------------------------------\n")
        
    except Exception as e:
        print("\n--- Scenario Generation FAILED ---")
        print(f"Error: {e}")
        print("----------------------------------\n")

if __name__ == "__main__":
    # Ensure you have your API key set before running this block
    # Note: If running this script directly, ensure you've called load_dotenv() 
    # and have either GOOGLE_API_KEY or GEMINI_API_KEY defined.
    asyncio.run(test_gemini_model())