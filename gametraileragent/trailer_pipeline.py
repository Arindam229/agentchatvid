import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    if hasattr(PIL.Image, 'Resampling'):
        PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
    elif hasattr(PIL.Image, 'LANCZOS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import os
import time
import random
import json
import requests
import subprocess
import re
import textwrap
import soundfile as sf
try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips, ImageClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
try:
    from youtube_uploader import upload_to_youtube
except ImportError:
    from youtube_uploader import upload_video as upload_to_youtube

def sanitize_text_for_pil(text: str) -> str:
    if not text:
        return ""
    replacements = {
        '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-',
        '\u2026': '...', '\u00a0': ' ',
        '’': "'", '‘': "'", '“': '"', '”': '"', '—': '-', '–': '-'
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode('ascii', errors='ignore').decode('ascii')

HISTORY_FILE = "trailer_history.json"
GENRES = ["Action", "Strategy", "RPG", "Indie", "Adventure", "Sports", "Simulation", "Racing"]

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"used_genres": [], "used_games": []}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def get_genre(history):
    available_genres = [g for g in GENRES if g not in history.get("used_genres", [])]
    if not available_genres:
        # Reset genres if all used
        history["used_genres"] = []
        available_genres = GENRES
    genre = random.choice(available_genres)
    history["used_genres"].append(genre)
    return genre

def fetch_top_games(genre, history, count=5):
    print(f"Fetching top games for genre: {genre}...")
    # Try genre first
    url = f"https://steamspy.com/api.php?request=genre&genre={genre}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        games = list(data.values()) if data and isinstance(data, dict) else []
    except Exception as e:
        print(f"Genre fetch error: {e}")
        games = []

    # If empty, try tag
    if not games:
        print(f"No games found for genre {genre}, trying tag...")
        url = f"https://steamspy.com/api.php?request=tag&tag={genre}"
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            games = list(data.values()) if data and isinstance(data, dict) else []
        except:
            pass

    # Final fallback: Get top 100 and filter manually or just return some
    if not games:
        print(f"Direct tag fetch failed for {genre}, falling back to trending games...")
        url = "https://steamspy.com/api.php?request=top100in2weeks"
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            if data and isinstance(data, dict):
                games = list(data.values())
                random.shuffle(games) # Randomize trending games
        except:
            pass
            
    if not games:
        return []
    
    used_games = history.get("used_games", [])
    valid_games = [g for g in games if str(g['appid']) not in used_games]
    
    return valid_games[:count]

def get_trailer_info(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    res = requests.get(url).json()
    if not res or str(app_id) not in res or not res[str(app_id)]['success']:
        return None
    
    data = res[str(app_id)]['data']
    movies = data.get('movies', [])
    if not movies:
        return None
        
    metacritic = data.get('metacritic', {}).get('score', 'N/A')
    
    movie = movies[0]
    trailer_url = movie.get('hls_h264')
    if not trailer_url:
        trailer_url = movie.get('mp4', {}).get('max')
        
    if not trailer_url:
        return None
        
    short_desc = data.get('short_description', 'Check out this amazing game!')
    short_desc = re.sub(r'<[^>]+>', '', short_desc).replace('&quot;', '"').strip()
    
    long_desc = data.get('about_the_game', data.get('detailed_description', ''))
    long_desc = re.sub(r'<[^>]+>', ' ', long_desc)
    long_desc = re.sub(r'\s+', ' ', long_desc).replace('&quot;', '"').strip()
    if not long_desc:
        long_desc = short_desc
        
    bg_url = data.get('background_raw') or data.get('header_image')
    
    return {
        "name": data.get('name'),
        "trailer_url": trailer_url,
        "rating": metacritic,
        "description": short_desc,
        "long_desc": long_desc,
        "bg_url": bg_url
    }

KOKORO_MODEL = None

def get_kokoro_model():
    global KOKORO_MODEL
    if KOKORO_MODEL is None:
        try:
            print("Loading Kokoro TTS model...")
            KOKORO_MODEL = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        except Exception as e:
            print(f"Failed to load Kokoro model: {e}")
    return KOKORO_MODEL

def normalize_tts_text(text):
    replacements = {
        r'\bPUBG\b': 'Pub G',
        r'\bGrand Theft Auto V\b': 'Grand Theft Auto 5',
        r'\bGTA V\b': 'GTA 5',
        r'\bGTA IV\b': 'GTA 4',
        r'\bFinal Fantasy XV\b': 'Final Fantasy 15',
        r'\bFinal Fantasy XIV\b': 'Final Fantasy 14',
        r'\bFinal Fantasy VII\b': 'Final Fantasy 7',
        r'\bResident Evil [Vv][Ii][Ii][Ii]\b': 'Resident Evil 8',
        r'\bResident Evil [Vv][Ii][Ii]\b': 'Resident Evil 7',
        r'\bCS:GO\b': 'CS GO',
        r'\bCSGO\b': 'CS GO',
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

def generate_voiceover(text, output_path, voice="am_adam"):
    text = normalize_tts_text(text)
    print(f"Generating voiceover for: {text[:30]}...")
    
    if Kokoro is not None:
        model = get_kokoro_model()
        if model:
            try:
                samples, sample_rate = model.create(
                    text,
                    voice=voice,
                    speed=1.0,
                    lang="en-us"
                )
                sf.write(output_path, samples, sample_rate)
                return True
            except Exception as e:
                print(f"Kokoro TTS generation failed: {e}")

    try:
        import asyncio
        import edge_tts
        communicate = edge_tts.Communicate(text, "en-US-AndrewNeural")
        asyncio.run(communicate.save(output_path))
        print(f"Edge-TTS voiceover saved to: {output_path}")
        return True
    except Exception as e:
        print(f"TTS generation failed completely: {e}")
        return False

def download_video(url, output_path):
    print(f"Downloading video from {url} to {output_path}")
    cmd = [
        "ffmpeg", "-y", "-i", url, 
        "-c", "copy", output_path
    ]
    for attempt in range(3):
        try:
            print(f"  Attempt {attempt+1}/3...")
            process = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 50000:
                print("  Download successful.")
                return True
        except subprocess.TimeoutExpired:
            print("  [!] Download timed out after 120 seconds.")
        except Exception as e:
            print(f"  [!] Download failed: {e}")
        time.sleep(2)
    return False

def create_intro_clip(genre):
    print("Creating intro sequence...")
    bg_path = "background.mp4"
    if not os.path.exists(bg_path):
        bg_path = "forza_gameplay.mkv"
        
    try:
        if os.path.exists(bg_path):
            clip = VideoFileClip(bg_path)
        else:
            from moviepy.editor import ColorClip
            clip = ColorClip(size=(1920, 1080), color=(20, 10, 35)).set_duration(15)
    except Exception as e:
        print(f"Could not load video intro background ({e}), using color clip...")
        from moviepy.editor import ColorClip
        clip = ColorClip(size=(1920, 1080), color=(20, 10, 35)).set_duration(15)
        
    max_start = max(0, clip.duration - 15)
    start_t = random.uniform(0, max_start)
    clip = clip.subclip(start_t, start_t + 15)
    
    clip_w, clip_h = clip.size
    target_ratio = 1920 / 1080
    clip_ratio = clip_w / clip_h
    
    if clip_ratio < target_ratio:
        clip = clip.resize(width=1920)
        offset = (clip.h - 1080) / 2
        clip = clip.crop(y1=offset, y2=offset+1080)
    else:
        clip = clip.resize(height=1080)
        offset = (clip.w - 1920) / 2
        clip = clip.crop(x1=offset, x2=offset+1920)
        
    tts_path = "temp_trailers/intro_tts.wav"
    script = f"Welcome back! Today we're counting down the top 5 {genre} games you absolutely must play. Let's dive right in!"
    
    if generate_voiceover(script, tts_path):
        voice_clip = AudioFileClip(tts_path)
        voice_clip = voice_clip.set_start(1.0)
        
        final_duration = voice_clip.duration + 1.5
        if clip.duration > final_duration:
            clip = clip.subclip(0, final_duration)
        
        if clip.audio:
            original_audio = clip.audio.volumex(0.3)
            final_audio = CompositeAudioClip([original_audio, voice_clip])
            clip = clip.set_audio(final_audio)
        else:
            clip = clip.set_audio(voice_clip.set_start(1.0))
            
    return clip

def create_cyberpunk_overlay(text, output_path="cyberpunk_overlay.png"):
    text = sanitize_text_for_pil(text)
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        font_path = os.path.join("..", "Roboto-Regular.ttf")
    try:
        font = ImageFont.truetype(font_path, 60)
        font_small = ImageFont.truetype(font_path, 45)
        font_desc = ImageFont.truetype(font_path, 30)
    except Exception:
        try:
            font = ImageFont.truetype("arialbd.ttf", 60)
            font_small = ImageFont.truetype("arialbd.ttf", 45)
            font_desc = ImageFont.truetype("arial.ttf", 30)
        except Exception:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_desc = ImageFont.load_default()
        
    lines = text.split('\n')
    
    dummy_img = Image.new('RGBA', (1, 1))
    d_dummy = ImageDraw.Draw(dummy_img)
    
    text_w = 0
    text_h = 0
    line_heights = []
    
    for i, line in enumerate(lines):
        if i == 0:
            current_font = font
            spacing = 10
        elif i == 1 and ("Metacritic:" in line or len(lines) == 2):
            current_font = font_small
            spacing = 25
        else:
            current_font = font_desc
            spacing = 8
            
        bbox = d_dummy.textbbox((0, 0), line, font=current_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        text_w = max(text_w, w)
        text_h += h + spacing
        line_heights.append((h, spacing))
    
    pad_x = 50
    pad_y = 30
    w = int(text_w + pad_x * 2)
    h = int(text_h + pad_y * 2)
    
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    cut = 35
    poly = [
        (cut, 0), (w, 0), 
        (w, h - cut), (w - cut, h), 
        (0, h), (0, cut)
    ]
    
    bg_color = (20, 10, 30, 150)
    d.polygon(poly, fill=bg_color)
    
    neon_cyan = (0, 240, 255, 255)
    neon_pink = (255, 20, 147, 255)
    neon_yellow = (252, 238, 9, 255)
    
    d.line(poly + [poly[0]], fill=(0, 240, 255, 80), width=12)
    d.line(poly + [poly[0]], fill=neon_cyan, width=3)
    
    d.rectangle([(w - cut - 40, h - 12), (w - cut - 10, h - 4)], fill=neon_pink)
    
    text_x = pad_x
    current_y = pad_y - 10
    
    for i, line in enumerate(lines):
        if i == 0:
            current_font = font
            fill_color = (255, 255, 255, 255)
        elif i == 1 and ("Metacritic:" in line or len(lines) == 2):
            current_font = font_small
            fill_color = neon_yellow
        else:
            current_font = font_desc
            fill_color = (220, 220, 220, 255)
            
        d.text((text_x + 3, current_y + 3), line, font=current_font, fill=(0, 0, 0, 180))
        d.text((text_x, current_y), line, font=current_font, fill=fill_color)
        
        h, spacing = line_heights[i]
        current_y += h + spacing
    
    img.save(output_path)
    return output_path

def create_gradient_mask(size):
    base = Image.new('RGBA', size, (0, 0, 0, 0))
    top = Image.new('RGBA', size, (0, 0, 0, 230))
    x = np.clip(np.linspace(255, -100, size[0]), 0, 255)
    mask_arr = np.tile(x, (size[1], 1)).astype(np.uint8)
    mask = Image.fromarray(mask_arr, mode='L')
    base.paste(top, (0, 0), mask)
    return base

def generate_thumbnail(bg_url, genre, output_path):
    genre = sanitize_text_for_pil(genre)
    print(f"Generating thumbnail from {bg_url}")
    try:
        res = requests.get(bg_url)
        img = Image.open(BytesIO(res.content)).convert("RGBA")
        
        target_ratio = 1920 / 1080
        img_ratio = img.width / img.height
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            offset = (img.width - new_w) // 2
            img = img.crop((offset, 0, offset + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            offset = (img.height - new_h) // 2
            img = img.crop((0, offset, img.width, offset + new_h))
            
        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
    except:
        img = Image.new('RGBA', (1920, 1080), (50, 20, 80))
        
    gradient = create_gradient_mask((1920, 1080))
    img.paste(gradient, (0, 0), gradient)
    
    d = ImageDraw.Draw(img, 'RGBA')
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        font_path = os.path.join("..", "Roboto-Regular.ttf")

    try:
        font_large = ImageFont.truetype("impact.ttf", 250)
    except:
        try:
            font_large = ImageFont.truetype(font_path, 200)
        except:
            try:
                font_large = ImageFont.truetype("arialbd.ttf", 200)
            except:
                font_large = ImageFont.load_default()
            
    text_top = "TOP 5"
    text_mid = f"{genre.upper()}"
    text_bot = "GAMES"
    
    def draw_text_with_shadow(draw, position, text, font, fill_color, stroke=12):
        x, y = position
        for adj_x in range(-stroke, stroke+1, 3):
            for adj_y in range(-stroke, stroke+1, 3):
                draw.text((x+adj_x, y+adj_y), text, font=font, fill=(0,0,0,255))
        draw.text(position, text, font=font, fill=fill_color)
        
    draw_text_with_shadow(d, (100, 180), text_top, font_large, (255, 255, 255))
    draw_text_with_shadow(d, (100, 430), text_mid, font_large, (252, 238, 9))
    draw_text_with_shadow(d, (100, 680), text_bot, font_large, (0, 240, 255))
    
    img = img.convert("RGB")
    img.save(output_path)
    return output_path

def create_overlay_clip(video_path, name, rating, description, long_desc):
    print(f"Adding overlay to {video_path}")
    clip = VideoFileClip(video_path)
    
    if clip.w != 1920 or clip.h != 1080:
        clip = clip.resize(width=1920)
        if clip.h > 1080:
            clip = clip.crop(y1=(clip.h-1080)/2, y2=(clip.h+1080)/2)
        elif clip.h < 1080:
            clip = clip.margin(top=int((1080-clip.h)/2), bottom=int((1080-clip.h)/2), color=(0,0,0))
    
    wrapped_desc = textwrap.fill(description, width=65)
    txt_text = f"{name}\nMetacritic: {rating}" if rating != 'N/A' else name
    txt_text += f"\n{wrapped_desc}"
    
    overlay_img_path = create_cyberpunk_overlay(txt_text, f"temp_overlay_{name[:5]}.png")
    
    txt_clip = ImageClip(overlay_img_path).set_duration(5)
    
    def make_slide(t, w, h):
        final_x = 50
        final_y = 1080 - h - 50
        if t < 1.0:
            progress = 1.0 - (1.0 - t)**3
            x = -w + (final_x + w) * progress
        elif t > 4.0:
            progress = (t - 4.0)**3
            x = final_x - (final_x + w) * progress
        else:
            x = final_x
        return (x, final_y)

    txt_clip = txt_clip.set_position(lambda t: make_slide(t, txt_clip.w, txt_clip.h))
    
    final_clip = CompositeVideoClip([clip, txt_clip])
    
    tts_path = f"temp_trailers/tts_{name[:5]}.wav"
    
    # Use the long description to ensure it keeps talking, but limit just in case it's an essay
    clean_long = long_desc[:1500]
    script = f"Next up is {name}. {clean_long}"
    
    if generate_voiceover(script, tts_path):
        voice_clip = AudioFileClip(tts_path)
        voice_clip = voice_clip.set_start(1.5)
        
        # Ensure voice clip doesn't extend beyond the video trailer
        if voice_clip.end > clip.duration:
            voice_clip = voice_clip.subclip(0, clip.duration - 1.5)
            # Add a slight fadeout so the sentence doesn't abruptly snap
            voice_clip = voice_clip.audio_fadeout(1.0)
            
        if final_clip.audio:
            original_audio = final_clip.audio.volumex(0.3)
            final_audio = CompositeAudioClip([original_audio, voice_clip]).set_duration(clip.duration)
            final_clip = final_clip.set_audio(final_audio)
        else:
            final_clip = final_clip.set_audio(voice_clip.set_start(1.5).set_duration(clip.duration))
            
    return final_clip

def main():
    history = load_history()
    genre = get_genre(history)
    print(f"Selected Genre: {genre}")
    
    games = fetch_top_games(genre, history, count=5)
    if not games:
        print("No valid games found.")
        return
        
    os.makedirs("temp_trailers", exist_ok=True)
    
    processed_clips = []
    current_time = 0
    timestamps = []
    
    intro_clip = create_intro_clip(genre)
    if intro_clip:
        processed_clips.append(intro_clip)
        current_time += intro_clip.duration
        
    first_bg_url = None
    
    final_video_path = f"top_{genre.lower()}_games.mp4"
    
    for i, game in enumerate(games):
        app_id = game['appid']
        print(f"Processing Game {i+1}: {game['name']}")
        info = get_trailer_info(app_id)
        
        if not info:
            print("No trailer available. Skipping.")
            continue
            
        raw_video = f"temp_trailers/raw_{app_id}.mp4"
        if not download_video(info['trailer_url'], raw_video):
            print("Download failed.")
            continue
            
        if not first_bg_url and info.get('bg_url'):
            first_bg_url = info['bg_url']
            
        clip = create_overlay_clip(raw_video, info['name'], info['rating'], info['description'], info['long_desc'])
        processed_clips.append(clip)
        
        mins = int(current_time // 60)
        secs = int(current_time % 60)
        desc_line = f"{mins:02d}:{secs:02d} - {info['name']}\nAbout: {info['description']}\n"
        timestamps.append(desc_line)
        
        current_time += clip.duration
        history["used_games"].append(str(app_id))
        
    if not processed_clips:
        print("No clips were successfully processed.")
        return
        
    thumbnail_path = "thumbnail.jpg"
    if first_bg_url:
        generate_thumbnail(first_bg_url, genre, thumbnail_path)
    else:
        thumbnail_path = None
        
    print("Concatenating all trailers...")
    final_compilation = concatenate_videoclips(processed_clips, method="compose")
    final_compilation.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=30, preset="medium", bitrate="12000k", logger=None)
    
    def close_clip_recursive(c):
        try:
            if hasattr(c, 'clips'):
                for child in c.clips:
                    close_clip_recursive(child)
            if hasattr(c, 'audio') and c.audio:
                close_clip_recursive(c.audio)
            c.close()
        except:
            pass

    close_clip_recursive(final_compilation)
    for clip in processed_clips:
        close_clip_recursive(clip)
        
    import gc
    gc.collect()
        
    print(f"Created {final_video_path}")
    
    title = f"Top 5 {genre} Games You MUST Play! (High Quality Trailers)"
    desc = f"Looking for the best {genre} games? Check out these amazing titles!\n\n"
    desc += "Timestamps:\n" + "\n".join(timestamps)
    desc += "\n\n#Gaming #Trailers #TopGames"
    
    print("Uploading to YouTube...")
    video_id = upload_to_youtube(
        video_path=final_video_path,
        title=title,
        description=desc,
        tags=["gaming", "trailers", genre.lower(), "top 5"],
        category_id="20",
        thumbnail_path=thumbnail_path,
        client_secrets_file="client_secrets.json",
        token_file="token.json"
    )
    
    if video_id:
        print(f"Successfully uploaded! Video ID: {video_id}")
        save_history(history)
        
        print("Cleaning up files...")
        import shutil
        import glob
        if os.path.exists(final_video_path):
            os.remove(final_video_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        if os.path.exists("temp_trailers"):
            import time
            for _ in range(3):
                try:
                    shutil.rmtree("temp_trailers")
                    break
                except Exception:
                    time.sleep(2)
            
        for overlay_file in glob.glob("temp_overlay_*.png"):
            try:
                os.remove(overlay_file)
            except:
                pass
    else:
        print("Upload failed.")

if __name__ == "__main__":
    main()
