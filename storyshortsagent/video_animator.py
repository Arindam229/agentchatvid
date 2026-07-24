"""
video_animator.py — Generates high-quality AI videos using CogVideoX-2B (local, RTX 4060).
Replaces basic SVD animation with state-of-the-art text-to-video.
"""
import os
import subprocess
import random
import torch
from pathlib import Path

# Use CogVideoX-2b for 8GB VRAM compatibility (RTX 4060)
COG_MODEL_ID = "THUDM/CogVideoX-2b"
_COG_PIPE = None

def get_cog_pipeline():
    """Load CogVideoX pipeline once and cache it."""
    global _COG_PIPE
    if _COG_PIPE is not None:
        return _COG_PIPE

    try:
        from diffusers import CogVideoXPipeline
        device = os.getenv("SVD_DEVICE", "cuda")
        print(f"[CogVideo] Loading CogVideoX-2B on {device}...")

        pipe = CogVideoXPipeline.from_pretrained(
            COG_MODEL_ID,
            torch_dtype=torch.float16
        )
        pipe = pipe.to(device)

        # Memory optimizations for 8GB VRAM
        pipe.enable_model_cpu_offload()
        pipe.vae.enable_tiling()
        
        _COG_PIPE = pipe
        print("[CogVideo] Pipeline loaded successfully.")
        return _COG_PIPE

    except Exception as e:
        print(f"[CogVideo] Failed to load pipeline: {e}")
        return None

def generate_video_clip(prompt: str, output_path: str, seed: int = 42) -> bool:
    """
    Generates a 2-second high-quality video clip from a text prompt.
    """
    pipe = get_cog_pipeline()
    if pipe is None:
        return False

    try:
        print(f"  [CogVideo] Generating: {prompt[:60]}...")
        
        # Enhanced prompt for CogVideoX quality
        enhanced_prompt = (
            f"{prompt}, cinematic 3D animation style, high quality, "
            f"detailed textures, 8k, vibrant lighting"
        )
        
        generator = torch.manual_seed(seed)
        
        # CogVideoX-2b parameters for RTX 4060
        video = pipe(
            prompt=enhanced_prompt,
            num_frames=24,           # ~2 seconds at 12fps
            num_inference_steps=30,  # Good balance of speed/quality
            guidance_scale=6.0,
            generator=generator,
        ).frames[0]

        # Export frames to MP4 via FFmpeg
        import tempfile, shutil
        tmp_dir = tempfile.mkdtemp()
        try:
            for i, frame in enumerate(video):
                frame_path = os.path.join(tmp_dir, f"frame_{i:04d}.png")
                frame.save(frame_path)

            # Scale to 720x1280 (portrait) for Shorts
            cmd = [
                "ffmpeg", "-y",
                "-framerate", "12",
                "-i", os.path.join(tmp_dir, "frame_%04d.png"),
                "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-crf", "19",
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"  [CogVideo] Saved: {output_path}")
            return True
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    except torch.cuda.OutOfMemoryError:
        print("  [CogVideo] CUDA OOM — consider reducing frames or using cpu offload")
        torch.cuda.empty_cache()
        return False
    except Exception as e:
        print(f"  [CogVideo] Error: {e}")
        return False

def animate_ken_burns(image_path: str, output_path: str, duration: float = 3.5) -> bool:
    """
    Ultra-reliable fallback: Cinematic Ken Burns effect on a static image.
    Used if GPU is busy or CogVideo fails.
    """
    styles = [
        f"zoompan=z='min(zoom+0.001,1.5)':d={int(duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
        f"zoompan=z='if(lte(zoom,1.0),1.5,max(1.0,zoom-0.001))':d={int(duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=720x1280",
    ]
    vf = random.choice(styles)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", f"{vf},fps=30", "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except:
        return False

def animate_images(
    image_paths: list[str],
    output_dir: str,
    prompts: list[str] = None,
    seed: int = 42,
    clip_duration: float = 3.5,
    use_svd: bool = True,
) -> list[str]:
    """
    Main entry point for the pipeline. 
    Tries CogVideoX first (Text-to-Video), falls back to Ken Burns.
    """
    os.makedirs(output_dir, exist_ok=True)
    video_clips = []

    # Pre-load CogVideoX if requested
    if use_svd:
        pipe = get_cog_pipeline()
        if pipe is None:
            use_svd = False

    for i, (img_path, prompt) in enumerate(zip(image_paths, prompts or [])):
        out_path = os.path.join(output_dir, f"scene_{i:02d}_anim.mp4")

        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            print(f"  [Animator] Reusing existing: {out_path}")
            video_clips.append(out_path)
            continue

        success = False
        if use_svd and prompt:
            # Try high-quality CogVideoX (Text-to-Video)
            success = generate_video_clip(prompt, out_path, seed=seed + i)

        if not success:
            # Fallback to Ken Burns on the generated image
            print(f"  [Animator] CogVideo failed/skipped for scene {i}, using Ken Burns fallback")
            success = animate_ken_burns(img_path, out_path, duration=clip_duration)

        if success:
            video_clips.append(out_path)
        else:
            print(f"  [Animator] FATAL for scene {i}")

    print(f"[Animator] Generated {len(video_clips)}/{len(image_paths)} clips")
    return video_clips


if __name__ == "__main__":
    # Test with existing images
    test_images = [p for p in Path("temp_story").glob("scene_*.jpg")]
    if test_images:
        animate_images(
            image_paths=[str(p) for p in sorted(test_images)],
            output_dir="temp_story",
            use_svd=True,
        )
    else:
        print("No scene images found. Run image_generator.py first.")
