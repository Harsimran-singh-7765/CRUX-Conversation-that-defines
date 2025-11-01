import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables (like your API key)
load_dotenv()

# Get your Google API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    exit(1)

# Initialize the GenAI client
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    print("GenAI client initialized successfully.")
except Exception as e:
    print(f"Error initializing GenAI client: {e}")
    exit(1)

async def test_gemini_model():
    
    # --- THIS IS THE FIX ---
    # Trying another model from your list: 'gemini-2.0-flash'
    model_name = "gemini-2.0-flash"
    # --- END FIX ---
    
    prompt = "Tell me a short story about a space-faring cat."

    print(f"\nAttempting to generate content with model: {model_name}")
    print(f"Prompt: {prompt}")

    try:
        def generate_sync():
            return client.models.generate_content(
                model=model_name,
                contents=[types.Part.from_text(text=prompt)],
                config=types.GenerateContentConfig(temperature=0.7)
            )

        response = await asyncio.to_thread(generate_sync)
        
        if response.text:
            print("\n--- AI Response (SUCCESS) ---")
            print(response.text)
            print("-----------------------------\n")
        else:
            print("AI Response was empty.")

    except Exception as e:
        print("\n--- AI Response (FAILED) ---")
        print(f"Error during content generation: {e}")
        print("This could indicate an issue with the model name, API key, or access permissions.")
        print("-----------------------------\n")

if __name__ == "__main__":
    asyncio.run(test_gemini_model())