"""
script_generator.py — Gemini-powered story + scene JSON generator
"""
import os
import json
import re
import random
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
_CLIENT = genai.Client(api_key=api_key)

# Try these models in order until one works (quota fallback)
MODELS = [
    "gemini-3.1-pro-preview",           # State of the art (May 2026)
    "gemini-3-flash-preview",           # High speed, next-gen
    "gemini-3.1-flash-lite",            # Ultra-light, massive quota
    "gemini-2.5-pro",                   # Extremely reliable pro model
    "gemini-2.5-flash",                 # Fast and efficient
    "gemini-2.0-flash",                 # Solid fallback
    "gemini-1.5-pro",                   # Legacy fallback
]

# Rotating pool of story archetypes for variety
STORY_ARCHETYPES = [
    "A child does something that should be impossible but pulls it off perfectly",
    "A regular person accidentally stumbles into a high-stakes situation and wins",
    "Someone is underestimated by everyone around them and proves them all wrong",
    "A series of wild coincidences leads to an unexpected happy ending",
    "A kid outsmarts adults in a high-pressure real-world situation",
    "Someone does something illegal but completely harmless and hilarious",
    "A total stranger saves the day with an unexpected skill",
    "A person makes a split-second decision that changes everything",
    "A prank or dare goes way further than expected but ends perfectly",
    "An ordinary day suddenly becomes an insane story no one believes",
    "A child prodigy is discovered in the most unexpected setting",
    "Someone completely unprepared somehow succeeds at an expert-level task",
    "A mix-up or mistake accidentally leads to something amazing",
    "A kid takes over an adult situation and handles it better than the adults",
    "The most unlikely person becomes an unexpected hero",
]

HISTORY_FILE = "story_history.json"


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"used_archetypes": [], "used_titles": []}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def pick_archetype(history):
    used = history.get("used_archetypes", [])
    available = [a for a in STORY_ARCHETYPES if a not in used]
    if not available:
        history["used_archetypes"] = []
        available = STORY_ARCHETYPES
    choice = random.choice(available)
    history["used_archetypes"].append(choice)
    return choice


def generate_story(topic_override=None):
    """
    Returns a dict with keys:
      title, youtube_title, narration, character_description,
      scenes (list of prompt strings), hashtags
    """
    history = load_history()
    archetype = topic_override or pick_archetype(history)

    seed = int(os.getenv("STORY_SEED", 42))

    prompt = f"""
You are a viral YouTube Shorts scriptwriter. Create a short story following this archetype:
"{archetype}"

Return ONLY valid JSON (no markdown, no code blocks) with this exact structure:
{{
  "title": "Short punchy title for the video (max 10 words)",
  "youtube_title": "YouTube title with emoji that gets clicks (max 100 chars)",
  "narration": "The full voiceover narration. Must be 150-180 words. Start with a STRONG hook in the first sentence. Use short punchy sentences. Build tension fast. End with a satisfying twist or reveal. Write it as if it actually happened — first or third person dramatic retelling. Natural spoken English only.",
  "character_description": "Visual description of the MAIN character for consistent image generation. Example: 'a 12-year-old boy with brown hair, wearing a red hoodie and jeans'. Keep it short and specific.",
  "scenes": [
    "Scene 1 image prompt (10-15 words describing what we see in this moment of the story)",
    "Scene 2 image prompt",
    "... (6-8 scenes total, one per major story beat)"
  ],
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}}

Rules for scene prompts:
- Each prompt describes ONE clear visual moment from the story
- Match the emotional tone of that moment (calm, tense, triumphant, etc.)
- Reference the character using their description naturally
- Do NOT include text, watermarks, or UI elements in scene descriptions
"""

    raw = None
    for model_name in MODELS:
        try:
            print(f"[Script] Trying {model_name}...")
            response = _CLIENT.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw = response.text.strip()
            if raw:
                break
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "exhausted" in msg.lower():
                print(f"[Script] Quota hit on {model_name}, switching model...")
                continue
            else:
                print(f"[Script] Error on {model_name}: {e}")
                continue

    if not raw:
        raise RuntimeError("All Gemini models failed — check quota or API key")

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    # Validate required keys
    required = ["title", "youtube_title", "narration", "character_description", "scenes", "hashtags"]
    for key in required:
        if key not in data:
            raise ValueError(f"Missing key in Gemini response: {key}")

    if len(data["scenes"]) < 4:
        raise ValueError(f"Too few scenes: {len(data['scenes'])}")

    history["used_titles"] = history.get("used_titles", []) + [data["title"]]
    save_history(history)

    print(f"[Script] Generated: {data['title']}")
    print(f"[Script] Scenes: {len(data['scenes'])}")
    print(f"[Script] Narration words: {len(data['narration'].split())}")
    return data


if __name__ == "__main__":
    story = generate_story()
    print(json.dumps(story, indent=2))
