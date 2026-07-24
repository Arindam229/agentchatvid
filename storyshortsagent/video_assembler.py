"""
video_assembler.py — Stitches animated clips + voiceover + captions into final Short
Uses pure FFmpeg for reliability and speed.
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path


def get_clip_duration(path: str) -> float:
    """Uses ffprobe to get video duration in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def get_audio_duration(path: str) -> float:
    """Uses ffprobe to get audio duration in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def concat_clips_to_duration(
    clip_paths: list[str],
    target_duration: float,
    output_path: str,
) -> bool:
    """
    Concatenates animated clips in sequence, looping the last clip if needed,
    until the total duration reaches the voiceover length.
    """
    if not clip_paths:
        return False

    # Build a concat list, cycling clips if there aren't enough
    tmp = tempfile.mkdtemp()
    try:
        concat_list_path = os.path.join(tmp, "concat.txt")
        total = 0.0
        entries = []

        clip_idx = 0
        while total < target_duration + 0.5:
            clip = clip_paths[clip_idx % len(clip_paths)]
            dur = get_clip_duration(clip)
            if dur <= 0:
                dur = 3.0
            entries.append(clip)
            total += dur
            clip_idx += 1
            if clip_idx > len(clip_paths) * 5:  # safety limit
                break

        with open(concat_list_path, "w") as f:
            for path in entries:
                # Use absolute path and escape backslashes for FFmpeg concat format
                abs_path = os.path.abspath(path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-t", str(target_duration),
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "ultrafast", "-crf", "20",
            "-r", "30",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[Assembler] Video track: {output_path} ({total:.1f}s trimmed to {target_duration:.1f}s)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[Assembler] Concat error: {e.stderr.decode()[-500:]}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def mix_audio(
    voiceover_path: str,
    sfx_path: str | None,
    output_path: str,
    sfx_volume: float = 0.18,
) -> bool:
    """
    Mixes voiceover with optional background SFX track.
    SFX is looped and faded in/out, voiceover is kept at full volume.
    """
    if sfx_path and os.path.exists(sfx_path):
        vo_dur = get_audio_duration(voiceover_path)
        cmd = [
            "ffmpeg", "-y",
            "-i", voiceover_path,
            "-stream_loop", "-1", "-i", sfx_path,
            "-filter_complex",
            (
                f"[1:a]volume={sfx_volume},afade=t=in:ss=0:d=1,"
                f"afade=t=out:st={vo_dur - 2}:d=2[sfx];"
                f"[0:a][sfx]amix=inputs=2:duration=first:normalize=0[out]"
            ),
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(vo_dur),
            output_path
        ]
    else:
        # Just re-encode voiceover as AAC
        cmd = [
            "ffmpeg", "-y",
            "-i", voiceover_path,
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[Assembler] Audio mixed: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Assembler] Audio mix error: {e.stderr.decode()[-300:]}")
        return False


def burn_captions(
    video_path: str,
    ass_path: str,
    audio_path: str,
    output_path: str,
) -> bool:
    """
    Burns ASS captions into the video and mixes in the audio.
    This is the final render step.
    """
    # Escape backslashes in path for FFmpeg filter (Windows)
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v", "-map", "1:a",
        "-shortest",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[Assembler] Final video: {output_path} ({size_mb:.1f} MB)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Assembler] Caption burn error: {e.stderr.decode()[-500:]}")
        return False


def assemble_video(
    animated_clips: list[str],
    voiceover_path: str,
    ass_path: str,
    output_path: str,
    sfx_path: str | None = None,
    work_dir: str = "temp_story",
) -> bool:
    """
    Full assembly pipeline:
    1. Concat clips to voiceover length
    2. Mix audio (voiceover + optional SFX)
    3. Burn captions → final MP4
    """
    os.makedirs(work_dir, exist_ok=True)

    vo_duration = get_audio_duration(voiceover_path)
    if vo_duration <= 0:
        print("[Assembler] Error: Could not read voiceover duration")
        return False

    print(f"[Assembler] Voiceover duration: {vo_duration:.2f}s")

    # Step 1: Build video track
    raw_video = os.path.join(work_dir, "raw_video.mp4")
    if not concat_clips_to_duration(animated_clips, vo_duration, raw_video):
        return False

    # Step 2: Mix audio
    mixed_audio = os.path.join(work_dir, "mixed_audio.aac")
    if not mix_audio(voiceover_path, sfx_path, mixed_audio):
        return False

    # Step 3: Burn captions + combine
    if not burn_captions(raw_video, ass_path, mixed_audio, output_path):
        return False

    return True


if __name__ == "__main__":
    # Quick test — assumes temp_story has everything
    clips = sorted(Path("temp_story").glob("scene_*_anim.mp4"))
    assemble_video(
        animated_clips=[str(c) for c in clips],
        voiceover_path="temp_story/voiceover.wav",
        ass_path="temp_story/captions.ass",
        output_path="temp_story/final_test.mp4",
        sfx_path=None,
    )
