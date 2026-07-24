"""
story_pipeline.py — Main orchestrator for the "insane story" YouTube Shorts pipeline.

Full flow (all free, no paid APIs):
  Gemini script → Kokoro voiceover → Pollinations images → SVD animation
  → faster-whisper captions → FFmpeg assembly → YouTube upload

Usage:
  python story_pipeline.py                     # Fully automatic (picks topic)
  python story_pipeline.py "a kid who..."      # Manual topic override
  python story_pipeline.py --no-upload         # Skip upload, just generate
  python story_pipeline.py --no-svd            # Skip SVD, use Ken Burns only
"""
import os
import sys
import time
import json
import shutil
import argparse
import re
import soundfile as sf
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Local imports ────────────────────────────────────────────────────────────
try:
    from script_generator import generate_story
    from image_generator import generate_scene_images
    from video_animator import animate_images
    from caption_generator import process_captions
    from video_assembler import assemble_video
except ImportError:
    from storyshortsagent.script_generator import generate_story
    from storyshortsagent.image_generator import generate_scene_images
    from storyshortsagent.video_animator import animate_images
    from storyshortsagent.caption_generator import process_captions
    from storyshortsagent.video_assembler import assemble_video

# ─── Paths ────────────────────────────────────────────────────────────────────
SPIDERMAN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KOKORO_MODEL = os.path.join(SPIDERMAN_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(SPIDERMAN_DIR, "voices-v1.0.bin")

# Chat Stories channel — client_secrets.json lives right here in storyshortsagent/
YT_SECRET = os.path.join(os.path.dirname(__file__), "client_secrets.json")
YT_TOKEN  = os.path.join(os.path.dirname(__file__), "token.json")

WORK_DIR = "temp_story"
OUTPUT_DIR = "output"
SFX_DIR = "sfx"

# ─── TTS ──────────────────────────────────────────────────────────────────────
_KOKORO = None


def get_kokoro():
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro
        print("[TTS] Loading Kokoro model...")
        _KOKORO = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
        print("[TTS] Kokoro ready.")
    return _KOKORO


def generate_voiceover(text: str, output_path: str) -> bool:
    import re as _re
    # Normalize Roman numerals for TTS
    replacements = {
        r'\bPUBG\b': 'Pub G', r'\bGTA V\b': 'GTA 5', r'\bGTA IV\b': 'GTA 4',
    }
    for pat, rep in replacements.items():
        text = _re.sub(pat, rep, text, flags=_re.IGNORECASE)

    voice = os.getenv("VOICEOVER_VOICE", "am_adam")
    speed = float(os.getenv("VOICEOVER_SPEED", "1.05"))

    try:
        model = get_kokoro()
        print(f"[TTS] Generating voiceover ({len(text.split())} words)...")
        samples, sample_rate = model.create(text, voice=voice, speed=speed, lang="en-us")
        sf.write(output_path, samples, sample_rate)
        print(f"[TTS] Voiceover saved: {output_path}")
        return True
    except Exception as e:
        print(f"[TTS] Kokoro unavailable/failed ({e}). Falling back to edge-tts...")
        try:
            import asyncio
            import edge_tts
            communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
            asyncio.run(communicate.save(output_path))
            print(f"[TTS] Edge-TTS Voiceover saved: {output_path}")
            return True
        except Exception as ex:
            print(f"[TTS] Edge-TTS Error: {ex}")
            return False


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_sfx_path() -> str | None:
    """Returns the ambient SFX path if one exists in the sfx/ folder."""
    sfx_candidates = ["ambient_tension.mp3", "background.mp3", "music.mp3"]
    for name in sfx_candidates:
        path = os.path.join(SFX_DIR, name)
        if os.path.exists(path):
            return path
    return None


def sanitize_filename(text: str) -> str:
    return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '_')[:60]


def upload_video(video_path: str, story: dict) -> str | None:
    try:
        from youtube_uploader import upload_to_youtube

        title = story.get("youtube_title", story["title"])
        narration_snippet = story["narration"][:200].rsplit(" ", 1)[0] + "..."
        hashtags = " ".join(story.get("hashtags", ["#Shorts", "#TrueStory"]))

        description = (
            f"{narration_snippet}\n\n"
            f"🎬 AI-generated story short\n\n"
            f"{hashtags}\n"
            f"#Shorts #AIStory #Viral"
        )

        tags = ["shorts", "story", "truestory", "viral", "ai"]
        tags += [h.lstrip("#").lower() for h in story.get("hashtags", [])]

        video_id = upload_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id="22",        # People & Blogs — fits story content
            client_secrets_file=YT_SECRET,
            token_file=YT_TOKEN,
        )
        return video_id
    except Exception as e:
        print(f"[Upload] Error: {e}")
        return None


# ─── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    topic_override: str | None = None,
    upload: bool = True,
    use_svd: bool = True,
    keep_temp: bool = False,
):
    start_time = time.time()
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.getenv("GITHUB_ACTIONS") == "true" and use_svd:
        print("[Pipeline] Running in Cloud CI (GitHub Actions). Disabling SVD (GPU-only) and enabling fast Ken Burns animation...")
        use_svd = False

    seed = int(os.getenv("STORY_SEED", 42))
    motion_bucket = int(os.getenv("SVD_MOTION_BUCKET", 80))

    # ── Step 1: Generate Script ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 1/6 — Generating script with Gemini...")
    print("="*60)
    story = generate_story(topic_override)

    story_slug = sanitize_filename(story["title"])
    final_output = os.path.join(OUTPUT_DIR, f"{story_slug}.mp4")

    if os.path.exists(final_output):
        print(f"[Pipeline] Output already exists: {final_output}")
        return final_output

    # Save story JSON for reference
    with open(os.path.join(WORK_DIR, "story.json"), "w") as f:
        json.dump(story, f, indent=2)

    # ── Step 2: Generate Voiceover ────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 2/6 — Generating voiceover with Kokoro TTS...")
    print("="*60)
    vo_path = os.path.join(WORK_DIR, "voiceover.wav")
    if not os.path.exists(vo_path):
        if not generate_voiceover(story["narration"], vo_path):
            print("[Pipeline] FATAL: Voiceover generation failed.")
            return None
    else:
        print(f"[TTS] Reusing existing voiceover: {vo_path}")

    # ── Step 3: Generate Scene Images ─────────────────────────────────────────
    print("\n" + "="*60)
    print(f"STEP 3/6 — Generating {len(story['scenes'])} scene images (Pollinations.ai)...")
    print("="*60)
    image_paths = generate_scene_images(
        scenes=story["scenes"],
        character_desc=story["character_description"],
        seed=seed,
        output_dir=WORK_DIR,
    )
    if not image_paths:
        print("[Pipeline] FATAL: No images generated.")
        return None

    # ── Step 4: Animate Images ────────────────────────────────────────────────
    print("\n" + "="*60)
    print(f"STEP 4/6 — Animating {len(image_paths)} scenes (SVD={'ON' if use_svd else 'OFF'})...")
    if use_svd:
        print("  ⏱ Estimated: ~45–60s per clip on RTX 4060")
    print("="*60)
    animated_clips = animate_images(
        image_paths=image_paths,
        output_dir=WORK_DIR,
        prompts=story["scenes"],
        seed=seed,
        clip_duration=3.5,
        use_svd=use_svd,
    )
    if not animated_clips:
        print("[Pipeline] FATAL: No animated clips generated.")
        return None

    # ── Step 5: Generate Captions ─────────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 5/6 — Transcribing voiceover for captions (faster-whisper)...")
    print("="*60)
    ass_path = os.path.join(WORK_DIR, "captions.ass")
    if not os.path.exists(ass_path):
        ass_path = process_captions(vo_path, WORK_DIR)
    else:
        print(f"[Caption] Reusing existing captions: {ass_path}")

    # ── Step 6: Assemble Final Video ──────────────────────────────────────────
    print("\n" + "="*60)
    print("STEP 6/6 — Assembling final video...")
    print("="*60)
    sfx_path = get_sfx_path()
    if sfx_path:
        print(f"[Assembler] Using SFX: {sfx_path}")
    else:
        print("[Assembler] No SFX found in sfx/ — voiceover only")

    tmp_final = os.path.join(WORK_DIR, "final_output.mp4")
    success = assemble_video(
        animated_clips=animated_clips,
        voiceover_path=vo_path,
        ass_path=ass_path,
        output_path=tmp_final,
        sfx_path=sfx_path,
        work_dir=WORK_DIR,
    )
    if not success:
        print("[Pipeline] FATAL: Video assembly failed.")
        return None

    shutil.copy2(tmp_final, final_output)
    elapsed = time.time() - start_time
    print(f"\n✅ Video ready: {final_output}")
    print(f"⏱ Total time: {elapsed/60:.1f} minutes")

    # ── Optional Upload ────────────────────────────────────────────────────────
    if upload:
        print("\n" + "="*60)
        print("UPLOADING to YouTube...")
        print("="*60)
        video_id = upload_video(final_output, story)
        if video_id:
            print(f"✅ Uploaded! https://youtube.com/shorts/{video_id}")
        else:
            print("⚠️  Upload failed. Video saved locally.")

    # ── Cleanup ────────────────────────────────────────────────────────────────
    if not keep_temp:
        print("\n[Pipeline] Cleaning up temp files...")
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        os.makedirs(WORK_DIR, exist_ok=True)

    return final_output


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Story Shorts Pipeline")
    parser.add_argument("topic", nargs="?", default=None, help="Optional topic/archetype override")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    parser.add_argument("--no-svd", action="store_true", help="Skip SVD, use Ken Burns only (faster)")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temp_story/ files after run")
    args = parser.parse_args()

    run_pipeline(
        topic_override=args.topic,
        upload=not args.no_upload,
        use_svd=not args.no_svd,
        keep_temp=args.keep_temp,
    )
