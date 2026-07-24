import asyncio
import json
import os
import urllib.request
import urllib.parse
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip, ColorClip
import soundfile as sf
try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

KOKORO_MODEL = None
def get_kokoro_model():
    global KOKORO_MODEL
    if Kokoro is None:
        return None
    if KOKORO_MODEL is None:
        model_path = r"C:\Users\Arind\OneDrive\Desktop\agents\spidermanagent\kokoro-v1.0.onnx"
        voices_path = r"C:\Users\Arind\OneDrive\Desktop\agents\spidermanagent\voices-v1.0.bin"
        if not os.path.exists(model_path):
            model_path = "kokoro-v1.0.onnx"
            voices_path = "voices-v1.0.bin"
        try:
            print("Loading Kokoro TTS model...")
            KOKORO_MODEL = Kokoro(model_path, voices_path)
        except Exception as e:
            print(f"Failed to load Kokoro model: {e}")
    return KOKORO_MODEL

# Screen Dimensions
W, H = 1080, 1920

# iMessage Frame Dimensions
F_WIDTH = 850
F_HEIGHT = 900
HEADER_H = 220
BODY_H = F_HEIGHT - HEADER_H
POS_Y = 400
POS_X = (W - F_WIDTH) // 2
MARGIN_X = 40

FONT_SIZE = 43
SCROLL_DURATION = 0.2
POP_DURATION = 0.15
LINE_SPACING = 5

def wrap_text(text, font, max_width):
    lines = []
    for paragraph in text.split('\n'):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = f"{current_line} {word}"
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines

def generate_imessage_assets():
    pad = 50
    # 1. Background with Drop Shadow
    shadow_img = Image.new('RGBA', (F_WIDTH + pad*2, F_HEIGHT + pad*2), (0,0,0,0))
    s_draw = ImageDraw.Draw(shadow_img)
    s_draw.rounded_rectangle([pad+15, pad+15, pad+F_WIDTH+15, pad+F_HEIGHT+15], radius=35, fill=(0,0,0,160))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(25))
    
    # Solid black rectangle for the body
    bg_draw = ImageDraw.Draw(shadow_img)
    bg_draw.rounded_rectangle([pad, pad, pad+F_WIDTH, pad+F_HEIGHT], radius=35, fill=(0,0,0,255))
    shadow_img.save("imessage_bg.png")
    
    # 2. Top Header overlay
    h_img = Image.new('RGBA', (F_WIDTH, HEADER_H), (0,0,0,0))
    h_draw = ImageDraw.Draw(h_img)
    head_color = (25, 25, 27, 255)
    # Draw rounded top, square bottom
    h_draw.rounded_rectangle([0, 0, F_WIDTH, HEADER_H*2], radius=35, fill=head_color)
    
    # Load fonts
    try:
        font_large = ImageFont.truetype("Roboto-Regular.ttf", 55)
        font_small = ImageFont.truetype("Roboto-Regular.ttf", 28)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    blue_color = (10, 132, 255)
    
    # "<"
    h_draw.text((40, 100), "<", font=font_large, fill=blue_color)
    
    # Video icon
    vx, vy = F_WIDTH - 110, 110
    vw, vh = 45, 30
    h_draw.rounded_rectangle([vx, vy, vx+vw, vy+vh], radius=6, outline=blue_color, width=3)
    h_draw.polygon([(vx+vw+4, vy+vh//2), (vx+vw+18, vy+2), (vx+vw+18, vy+vh-2)], outline=blue_color, width=3)
    
    # Profile pic
    cx, cy = F_WIDTH//2, 80
    r = 50
    h_draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(160, 160, 165))
    h_draw.ellipse([cx-20, cy-30, cx+20, cy+5], fill=(225, 225, 225))
    h_draw.chord([cx-38, cy+10, cx+38, cy+120], 180, 360, fill=(225, 225, 225))
    
    # Name
    title = "+1 943-667-7243 \u203A"
    bbox = font_small.getbbox(title)
    h_draw.text(( (F_WIDTH - (bbox[2]-bbox[0]))//2, cy + r + 15), title, font=font_small, fill=(200, 200, 200))
    
    # separator
    h_draw.line([(0, HEADER_H-1), (F_WIDTH, HEADER_H-1)], fill=(40, 40, 40, 255), width=2)
    h_img.save("imessage_header.png")

def create_caption(text):
    max_w = 800
    try:
        font = ImageFont.truetype("Roboto-Regular.ttf", 40)
    except:
        font = ImageFont.load_default()
        
    lines = wrap_text(text, font, max_w - 60)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    
    text_w = 0
    for line in lines:
        bbox = font.getbbox(line)
        text_w = max(text_w, bbox[2] - bbox[0])
        
    img_w = text_w + 60
    img_h = line_h * len(lines) + 10 * (len(lines)-1) + 30
    
    img = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0,0,img_w,img_h], radius=12, fill=(15,15,15,245))
    
    y = 15
    for line in lines:
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        draw.text( ((img_w - lw)//2, y), line, font=font, fill=(255,255,255))
        y += line_h + 10
        
    return img

import random
import time

def download_stock_image(keyword, filepath, width=400, height=400):
    # Clean up keyword (remove underscores, etc)
    clean_keyword = keyword.replace("_", " ").strip()
    
    for attempt in range(4): # Try 4 times (2 AI, 2 Stock)
        seed = random.randint(1, 999999)
        
        # Strategy:
        # Attempt 1: Full Keyword (AI)
        # Attempt 2: Full Keyword (AI, with 10s backoff)
        # Attempt 3: LoremFlickr (Stock photo via keyword)
        # Attempt 4: Picsum (Random stock photo guarantee)
        
        current_keyword = clean_keyword
        use_fallback_source = False
        url = ""
        
        if attempt == 0:
            time.sleep(5) # Base rate limit
        elif attempt == 1:
            print("    [#] Applying 10-second backoff for AI generator...")
            time.sleep(10) # Exponential backoff
        elif attempt == 2:
            current_keyword = clean_keyword.split()[-1]
            print(f"    [#] AI Failed. Fallback 1: Searching LoremFlickr for '{current_keyword}'...")
            url = f"https://loremflickr.com/{width}/{height}/{urllib.parse.quote(current_keyword)}?lock={seed}"
            use_fallback_source = True
            time.sleep(2)
        elif attempt == 3:
            print(f"    [#] Fallback 2: Grabbing guaranteed random photo from Picsum...")
            url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
            use_fallback_source = True
            time.sleep(2)
            
        if not use_fallback_source:
             safe_keyword = urllib.parse.quote(current_keyword + ", taken with an iphone with flash, realistic photography, unedited snap")
             url = f"https://image.pollinations.ai/prompt/{safe_keyword}?width={width}&height={height}&nologo=true&seed={seed}"
        
        if not use_fallback_source:
            print(f"    [#] Downloading AI image for: '{current_keyword}' (Attempt {attempt+1})...")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=35) as response:
                with open(filepath, 'wb') as f:
                    f.write(response.read())
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"    [#] Success: '{current_keyword}' fetched.")
                return True
        except Exception as e:
            print(f"    [#] Attempt {attempt+1} failed for '{current_keyword}': {e}")
    
    return False

def create_bubble(msg, is_sender, font_path, msg_index):
    text = msg['message']
    has_image = 'image_keyword' in msg
    font = ImageFont.truetype(font_path, FONT_SIZE)
    lines = wrap_text(text, font, int(F_WIDTH * 0.75) - 80)
    
    ascent, descent = font.getmetrics()
    line_block_h = ascent + descent
    
    text_w = 0
    for line in lines:
        bbox = font.getbbox(line)
        text_w = max(text_w, bbox[2] - bbox[0])
        
    total_text_h = line_block_h * len(lines) + LINE_SPACING * (len(lines) - 1)
    bubble_w = text_w + 80
    
    img_attachment = None
    if has_image:
        image_path = f"fetched_img_{msg_index}.png"
        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            download_stock_image(msg['image_keyword'], image_path)
        
        if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
            try:
                img_attachment = Image.open(image_path).convert("RGBA")
                mask = Image.new("L", img_attachment.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, img_attachment.width, img_attachment.height], radius=25, fill=255)
                
                result_img = Image.new("RGBA", img_attachment.size, (0,0,0,0))
                result_img.paste(img_attachment, (0,0), mask=mask)
                img_attachment = result_img
                
                bubble_w = max(bubble_w, img_attachment.width + 40)
            except:
                img_attachment = None
                
    bubble_h = total_text_h + 60
    if img_attachment:
        bubble_h += img_attachment.height + 20
    
    bg_color = (0, 122, 255) if is_sender else (38, 38, 40)
    text_color = (255, 255, 255) 
    
    img_w = bubble_w + 20
    img_h = bubble_h + 15
    
    scale_factor = 2
    img = Image.new('RGBA', (img_w * scale_factor, img_h * scale_factor), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    sw = bubble_w * scale_factor
    sh = bubble_h * scale_factor
    rx = 35 * scale_factor
    
    if is_sender:
        rect_box = [0, 0, sw, sh]
    else:
        rect_box = [20 * scale_factor, 0, sw + 20 * scale_factor, sh]
        
    draw.rounded_rectangle(rect_box, radius=rx, fill=bg_color)
    
    if is_sender:
        draw.polygon([(sw - rx + 10, sh), (sw + 15, sh), (sw - 10, sh - 25)], fill=bg_color)
    else:
        draw.polygon([(rect_box[0] + rx - 10, sh), (rect_box[0] - 15, sh), (rect_box[0] + 10, sh - 25)], fill=bg_color)
    
    current_y = rect_box[1] + 30 * scale_factor
    
    if img_attachment:
        scaled_att = img_attachment.resize((img_attachment.width * scale_factor, img_attachment.height * scale_factor), Image.Resampling.LANCZOS)
        att_x = rect_box[0] + (sw - scaled_att.width) // 2
        img.paste(scaled_att, (int(att_x), int(current_y)), scaled_att)
        current_y += scaled_att.height + 20 * scale_factor
        
    font_scaled = ImageFont.truetype(font_path, FONT_SIZE * scale_factor)
    for line in lines:
        bbox = font_scaled.getbbox(line)
        line_w = bbox[2] - bbox[0]
        x_text = rect_box[0] + (sw - line_w) // 2
        draw.text((x_text, current_y), line, font=font_scaled, fill=text_color)
        current_y += (line_block_h + LINE_SPACING) * scale_factor
        
    img = img.resize((img_w, img_h), Image.Resampling.LANCZOS)
    return img
async def main():
    if not os.path.exists("input.json"):
        return
        
    with open('input.json', 'r') as f:
        full_data = json.load(f)
        data = full_data['messages'] if isinstance(full_data, dict) else full_data
    
    if not data:
        return

    generate_imessage_assets()
    
    # Store global owner name from the first message
    owner_name = data[0]['sender']
    
    print("Pre-calculating durations and generating audios...")
    msg_data = []
    
    for i, msg in enumerate(data):
        is_sender = msg['sender'] == owner_name
        audio_file = f"audio_{i}.mp3"
        
        # Robust audio generation with retries
        valid_gen = False
        if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
            try:
                audio_clip = AudioFileClip(audio_file)
                valid_gen = True
            except:
                print(f"  [!] Existing {audio_file} is corrupted. Deleting...")
                os.remove(audio_file)
        
        if not valid_gen:
            for attempt in range(5):
                try:
                    model = get_kokoro_model()
                    if model:
                        voice_mapping = "am_adam"
                        if "female" in msg.get('voice_type', '').lower() or "Aria" in msg.get('voice_type', '') or "Jenny" in msg.get('voice_type', ''):
                            voice_mapping = "af_sarah"
                        
                        samples, sample_rate = model.create(msg['message'], voice=voice_mapping, speed=1.15, lang="en-us")
                        sf.write(audio_file, samples, sample_rate)
                    else:
                        import edge_tts
                        voice = msg.get('voice_type', 'en-US-AndrewNeural')
                        communicate = edge_tts.Communicate(msg['message'], voice)
                        await communicate.save(audio_file)
                        
                    if os.path.exists(audio_file) and os.path.getsize(audio_file) > 0:
                        try:
                            audio_clip = AudioFileClip(audio_file)
                            valid_gen = True
                            # Delay after success to prevent spamming
                            await asyncio.sleep(1.0)
                            break
                        except:
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                except asyncio.TimeoutError:
                    print(f"  [!] Audio gen attempt {attempt+1} timed out for msg {i}.")
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                except Exception as e:
                    print(f"  [!] Audio gen attempt {attempt+1} failed for msg {i}: {e}")
                
                if attempt < 4:
                    backoff = (attempt + 1) * 4  # 4s, 8s, 12s, 16s
                    print(f"  [#] Waiting {backoff}s before retry due to edge-tts rate limits...")
                    await asyncio.sleep(backoff)
            
        if not valid_gen:
            print(f"  [!] Warning: Using silent fallback for msg {i}")
            import numpy as np
            from moviepy.audio.AudioClip import AudioArrayClip
            silent_samples = np.zeros((int(44100 * 0.3), 2), dtype=np.float32)
            audio_clip = AudioArrayClip(silent_samples, fps=44100)
            duration = 0.3
        else:
            duration = audio_clip.duration + 0.05
            
        # Create bubble to get height
        if 'image_keyword' in msg:
            print(f"  [+] Message {i} includes image request: '{msg['image_keyword']}'")
        
        img = create_bubble(msg, is_sender, "Roboto-Regular.ttf", i)
        img_path = f"bubble_{i}.png"
        img.save(img_path)
        
        msg_data.append({
            'index': i,
            'msg': msg,
            'duration': duration,
            'height': img.height,
            'img_path': img_path,
            'audio_clip': audio_clip,
            'is_sender': is_sender
        })

    # Segment messages into parts
    segments = []
    current_segment = []
    current_dur = 0.5 # Start buffer
    
    for item in msg_data:
        # If adding this message exceeds 58 seconds, start a new segment
        if current_dur + item['duration'] > 58 and current_segment:
            segments.append(current_segment)
            current_segment = [item]
            current_dur = 0.5 + item['duration']
        else:
            current_segment.append(item)
            current_dur += item['duration']
            
    if current_segment:
        segments.append(current_segment)

    print(f"Split story into {len(segments)} part(s).")
    
    for seg_idx, segment in enumerate(segments):
        part_num = seg_idx + 1
        print(f"Rendering Part {part_num}...")
        
        clips = []
        audios = []
        captions = []
        t_start = 0.5
        t_starts = []
        heights = []
        
        # We need the relative data for this segment's animations
        segment_msgs = [item['msg'] for item in segment]
        
        for i, item in enumerate(segment):
            idx = item['index']
            msg = item['msg']
            audio_clip = item['audio_clip']
            is_sender = item['is_sender']
            img_path = item['img_path']
            
            # Pop sound
            try:
                pop_clip = AudioFileClip("pop.mp3").set_start(t_start)
                audios.append(pop_clip)
            except:
                pass
            
            # Message audio
            if audio_clip is not None:
                audios.append(audio_clip.set_start(t_start + 0.1))
            
            # Balloon clip
            clip = ImageClip(img_path).set_start(t_start)
            
            # Caption box
            cap_img = create_caption(msg['message'])
            cap_path = f"caption_{idx}.png"
            cap_img.save(cap_path)
            cap_clip = ImageClip(cap_path).set_start(t_start).set_duration(audio_clip.duration + 0.3).set_position(('center', 150))
            captions.append(cap_clip)
            
            t_starts.append(t_start)
            heights.append(item['height'])
            clips.append(clip)
            t_start += item['duration']
            
        total_duration = t_start + 1.0
        
        # BG setup
        try:
            bg = VideoFileClip("background.mp4")
            if bg.duration < total_duration:
                import moviepy.video.fx.all as vfx
                bg = vfx.loop(bg, duration=total_duration)
            else:
                bg = bg.subclip(0, total_duration)
            
            bg_w, bg_h = bg.size
            if bg_w > int(bg_h * 9 / 16):
                x_center = bg_w / 2
                bg = bg.crop(x1=x_center - (bg_h*9/16)/2, y1=0, width=bg_h*9/16, height=bg_h)
            bg = bg.resize(newsize=(W, H))
        except:
            bg = ColorClip(size=(W, H), color=(30, 30, 30)).set_duration(total_duration)
            
        dark = ColorClip(size=(W, H), color=(0,0,0)).set_opacity(0.3).set_duration(total_duration)
        
        # Animated bubbles
        animated_clips = []
        for i, item in enumerate(segment):
            clip = clips[i].set_duration(total_duration - t_starts[i])
            
            def make_pos(idx_in_seg=i, img_w=clip.w, img_h=clip.h, is_sender=item['is_sender']):
                lcl_spawn_y = BODY_H - 40 - img_h
                def pos(t):
                    t_global = t + t_starts[idx_in_seg]
                    scale = 1.0
                    if t < POP_DURATION:
                        scale = 0.5 + 0.5 * (t / POP_DURATION)
                        
                    total_shift = 0
                    for j in range(idx_in_seg + 1, len(segment)):
                        gap = 5 if segment[j]['is_sender'] == segment[j-1]['is_sender'] else 30
                        shift_amount = (heights[j] - 15) + gap
                        t_j = t_starts[j]
                        if t_global >= t_j + SCROLL_DURATION:
                            total_shift += shift_amount
                        elif t_global > t_j:
                            total_shift += shift_amount * ((t_global - t_j) / SCROLL_DURATION)
                            
                    current_w = img_w * scale
                    current_h = img_h * scale
                    cur_y = lcl_spawn_y + (img_h - current_h) - total_shift
                    if is_sender:
                        cur_x = F_WIDTH - MARGIN_X - current_w
                    else:
                        cur_x = MARGIN_X
                    return (cur_x, cur_y)
                return pos
                
            def make_scale():
                def scale_func(t):
                    if t < 0: return 0.5
                    if t >= POP_DURATION: return 1.0
                    return 0.5 + 0.5 * (t / POP_DURATION)
                return scale_func
                
            scaled_clip = clip.resize(make_scale()).set_position(make_pos())
            animated_clips.append(scaled_clip)
            
        # Composite components
        bg_frame = ImageClip("imessage_bg.png").set_duration(total_duration).set_position((POS_X - 50, POS_Y - 50))
        bubbles_canvas = CompositeVideoClip(animated_clips, size=(F_WIDTH, BODY_H))
        bubbles_canvas = bubbles_canvas.set_duration(total_duration).set_position((POS_X, POS_Y + HEADER_H))
        header_frame = ImageClip("imessage_header.png").set_duration(total_duration).set_position((POS_X, POS_Y))
        
        final_video = CompositeVideoClip([bg, dark, bg_frame, bubbles_canvas, header_frame] + captions)
        
        # Audio
        try:
            import moviepy.audio.fx.all as afx
            bg_audio = AudioFileClip("We Don T Talk Anymore Ringtone Instrumental.mp3")
            if bg_audio.duration < total_duration:
                bg_audio = afx.audio_loop(bg_audio, duration=total_duration)
            else:
                bg_audio = bg_audio.subclip(0, total_duration)
            bg_audio = bg_audio.fx(afx.volumex, 0.15)
            audios.append(bg_audio)
        except Exception as e:
            print(f"Warning: Part {part_num} audio fail: {e}")
            
        final_video = final_video.set_audio(CompositeAudioClip(audios))
        
        # Output filename
        out_file = f"final_part{part_num}.mp4" if len(segments) > 1 else "final.mp4"
        try:
            final_video.write_videofile(out_file, fps=24, codec="h264_nvenc", audio_codec="aac", threads=12, preset="fast", ffmpeg_params=["-pix_fmt", "yuv420p"])
        except Exception as e:
            print(f"NVENC encoding failed/unavailable ({e}). Falling back to libx264 CPU encoder...")
            final_video.write_videofile(out_file, fps=24, codec="libx264", audio_codec="aac", threads=4, preset="fast", ffmpeg_params=["-pix_fmt", "yuv420p"])
        print(f"Part {part_num} complete.")

if __name__ == "__main__":
    asyncio.run(main())
