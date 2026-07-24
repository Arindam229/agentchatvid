"""
image_generator.py — Free high-quality image generation via Pollinations.ai (FLUX)
Character consistency via locked character prefix in every prompt.
"""
import os
import time
import requests
from urllib.parse import quote
from pathlib import Path

# Video generation settings
WIDTH = 720
HEIGHT = 1280
MODEL = "flux"
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

STYLE_SUFFIX = (
    "cinematic 3D animation style, Pixar movie aesthetic, "
    "vibrant colors, dramatic studio lighting, 8k resolution, "
    "highly detailed, 9:16 vertical format, sharp focus, "
    "professional digital art, no text, no watermarks"
)


def build_prompt(scene_prompt: str, character_desc: str) -> str:
    """
    Injects the character description and style suffix into every scene prompt.
    """
    return f"{character_desc}, {scene_prompt}, {STYLE_SUFFIX}"


def fetch_image(prompt: str, seed: int, output_path: str, retries: int = 5) -> bool:
    """
    Downloads one image from Pollinations.ai.
    Returns True on success.
    """
    encoded = quote(prompt)
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width={WIDTH}&height={HEIGHT}&model={MODEL}"
        f"&seed={seed}&nologo=true&enhance=true"
    )

    for attempt in range(1, retries + 1):
        try:
            print(f"  [Image] Pollinations Attempt {attempt}/{retries}: {prompt[:60]}...")
            resp = requests.get(url, timeout=120, stream=True)
            
            if resp.status_code == 429:
                wait_time = 30 * attempt  # 30, 60, 90...
                print(f"  [Image] Rate limited (429). Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
                
            resp.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            size = os.path.getsize(output_path)
            if size < 10000:  # Valid images are usually > 10KB
                print(f"  [Image] Warning: file too small ({size} bytes), retrying...")
                time.sleep(5)
                continue

            print(f"  [Image] Saved: {output_path} ({size // 1024} KB)")
            return True

        except Exception as e:
            print(f"  [Image] Error on attempt {attempt}: {e}")
            wait_time = 5 * attempt
            time.sleep(wait_time)

    return False


def generate_scene_images(
    scenes: list[str],
    character_desc: str,
    seed: int,
    output_dir: str,
) -> list[str]:
    """
    Generates one image per scene prompt.
    Returns list of paths to successfully generated images.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    for i, scene in enumerate(scenes):
        output_path = os.path.join(output_dir, f"scene_{i:02d}.jpg")

        # Reuse existing image if already generated (resume support)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [Image] Reusing existing: {output_path}")
            image_paths.append(output_path)
            continue

        full_prompt = build_prompt(scene, character_desc)
        # Vary seed slightly per scene so backgrounds differ
        scene_seed = seed + i

        success = fetch_image(full_prompt, scene_seed, output_path)
        if success:
            image_paths.append(output_path)
            # Small delay between successful requests to avoid rapid-fire rate limits
            time.sleep(2)
        else:
            print(f"  [Image] FAILED for scene {i}: {scene[:50]}")

    print(f"[Image] Generated {len(image_paths)}/{len(scenes)} images")
    return image_paths


if __name__ == "__main__":
    # Quick test
    test_scenes = [
        "A boy sitting at a kitchen table staring at car keys",
    ]
    paths = generate_scene_images(
        scenes=test_scenes,
        character_desc="a 17-year-old boy with messy blonde hair wearing a navy windbreaker",
        seed=42,
        output_dir="temp_story",
    )
    print("Generated:", paths)
