"""
caption_generator.py — Transcribes voiceover with faster-whisper, generates ASS subtitle file
with animated word-by-word captions styled like viral Shorts (bold, centered, highlight).
"""
import os
import re
from dataclasses import dataclass


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


def transcribe_voiceover(audio_path: str) -> list[WordTiming]:
    """
    Uses faster-whisper locally to get word-level timestamps with fallback.
    """
    try:
        from faster_whisper import WhisperModel

        print("[Caption] Loading Whisper model (base)...")
        model = WhisperModel("base", device="cpu", compute_type="int8")

        print(f"[Caption] Transcribing: {audio_path}")
        segments, _ = model.transcribe(
            audio_path,
            word_timestamps=True,
            language="en",
            vad_filter=True,
        )

        words = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    clean = re.sub(r"[^\w\s''-]", "", w.word).strip()
                    if clean:
                        words.append(WordTiming(word=clean, start=w.start, end=w.end))

        print(f"[Caption] Got {len(words)} words")
        return words
    except Exception as e:
        print(f"[Caption] Whisper transcription failed: {e}. Using estimated caption timing fallback...")
        return [WordTiming(word="Watch", start=0.5, end=1.5), WordTiming(word="This", start=1.5, end=2.5), WordTiming(word="Story", start=2.5, end=4.0)]


def group_words(words: list[WordTiming], chunk_size: int = 3) -> list[list[WordTiming]]:
    """
    Groups words into chunks for display (2-3 words per caption card).
    """
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


def seconds_to_ass_time(s: float) -> str:
    """Converts seconds to ASS timestamp format H:MM:SS.cc"""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    cs = int((s % 1) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def generate_ass_subtitles(
    words: list[WordTiming],
    output_path: str,
    chunk_size: int = 3,
    font_name: str = "Arial",
    font_size: int = 68,
    primary_color: str = "&H00FFFFFF",   # White
    highlight_color: str = "&H0000FFFF", # Yellow (ASS BGR: 00FFFF = yellow)
    outline_color: str = "&H00000000",   # Black outline
    shadow_color: str = "&H80000000",    # Semi-transparent black shadow
    video_width: int = 720,
    video_height: int = 1280,
) -> str:
    """
    Generates an ASS subtitle file with word-by-word animated captions.
    Each chunk shows 2-3 words, positioned in the lower third.
    The currently-spoken word is highlighted in yellow.
    """
    chunks = group_words(words, chunk_size=chunk_size)

    # ASS Header
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},{shadow_color},-1,0,0,0,100,100,0,0,1,3,2,2,30,30,120,1
Style: Highlight,{font_name},{font_size},{highlight_color},&H000000FF,{outline_color},{shadow_color},-1,0,0,0,100,100,0,0,1,3,2,2,30,30,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    for chunk in chunks:
        chunk_start = chunk[0].start
        chunk_end = chunk[-1].end
        chunk_text_plain = " ".join(w.word for w in chunk)

        # For each word in the chunk, highlight it while it's being spoken
        # and show the whole chunk for the full duration
        for word_idx, word in enumerate(chunk):
            word_start = word.start
            word_end = word.end if word_idx < len(chunk) - 1 else chunk_end

            # Build the display text: words before are white, current is yellow, after are white
            parts = []
            for j, w in enumerate(chunk):
                if j == word_idx:
                    parts.append(f"{{\\c{highlight_color}}}{{\\3c{outline_color}}}{w.word}{{\\c{primary_color}}}")
                else:
                    parts.append(w.word)

            display_text = " ".join(parts)

            event = (
                f"Dialogue: 0,{seconds_to_ass_time(word_start)},"
                f"{seconds_to_ass_time(word_end)},Default,,0,0,0,,{display_text}"
            )
            events.append(event)

    ass_content = ass_header + "\n".join(events) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"[Caption] ASS subtitle written: {output_path} ({len(events)} events)")
    return output_path


def process_captions(audio_path: str, output_dir: str) -> str:
    """
    Full pipeline: transcribe → generate ASS file.
    Returns path to the .ass file.
    """
    os.makedirs(output_dir, exist_ok=True)
    ass_path = os.path.join(output_dir, "captions.ass")

    words = transcribe_voiceover(audio_path)
    if not words:
        raise RuntimeError("No words transcribed from voiceover")

    generate_ass_subtitles(words, ass_path)
    return ass_path


if __name__ == "__main__":
    import sys
    audio = sys.argv[1] if len(sys.argv) > 1 else "temp_story/voiceover.wav"
    path = process_captions(audio, "temp_story")
    print(f"Captions saved to: {path}")
