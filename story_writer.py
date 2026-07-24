from google import genai
import os
import json
from dotenv import load_dotenv

def write_story():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env. Please create a .env file containing your API Key.")
        exit(1)
        
    client = genai.Client(api_key=api_key)
    # Using Gemini 2.5 flash if available.
    model_id = 'gemini-2.5-flash'
    
    prompt = """
    Write an extremely dramatic, spicy, and scandalous text conversation between two people. 
    STRICT REQUIREMENT: The conversation must be fast-paced and engaging.
    Limit the generation to approximately 25 to 35 text messages to keep it snappy.
    
    VOICE SELECTION:
    - Use "en-US-AvaNeural" for a female voice (very expressive and modern).
    - Use "en-US-AndrewNeural" for a male voice (expressive and modern).
    - Use "en-GB-SoniaNeural" if you need a British female voice.
    
    IMPORTANT ADDITION: Characters MUST send photos (MMS) to each other! 
    MANDATORY: Include an `image_keyword` field in at least 2 to 3 messages where characters send evidence, photos, or proof.
    The `image_keyword` MUST be a highly detailed, explicit, photorealistic prompt describing the exact scene and object (e.g., "A macro photography shot of a bright red lipstick kiss mark on the collar of a folded white dress shirt", "A shiny gold Chanel pearl earring resting on the black leather dashboard of a luxury car, taken with an iPhone"). Focus heavily on context, positioning, and realism. Do NOT use short abstract phrases.
    
    OUTPUT STRUCTURE:
    Return a JSON object with:
    1. "video_title": A catchy, clickbaity YouTube title (max 60 chars).
    2. "video_description": A short, engaging description for YouTube Shorts with hashtags.
    3. "messages": The array of conversation objects.
    
    Example Structure:
    {
      "video_title": "HE ADMITTED IT! 😱 #betrayal #texts",
      "video_description": "She thought they were friends... she was wrong. #texts #shorts #drama",
      "messages": [
        { "sender": "Liam", "message": "I know what you did.", "voice_type": "en-US-AndrewNeural" },
        ...
      ]
    }
    Use highly realistic, gripping, and FAST-PACED dialogue.
    """
    
    print("Prompting Gemini AI for a new script...")
    
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            break
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                print(f"Quota exceeded. Retrying in 30 seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(30)
            else:
                print(f"ERROR: Gemini API call failed: {e}")
                exit(1)
        
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    try:
        data = json.loads(text.strip())
        with open('input.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("New AI Story successfully written to input.json")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON form: {e}\n{text}")
        exit(1)
        
if __name__ == "__main__":
    write_story()
