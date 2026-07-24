import os
import subprocess
import time

def run_script(script_name):
    print(f"\n======================================")
    print(f"  Executing Phase: {script_name}")
    print(f"======================================")
    result = subprocess.run(["python", script_name])
    if result.returncode != 0:
        print(f"\n[!] Error executing {script_name}. Pipeline Stopped.")
        exit(1)

def main():
    print("Starting Fully Autonomous Text-Video Pipeline...\n")
    
    # Execute AI Writing
    run_script("story_writer.py")
    
    # Clear out previous artifacts to ensure no lingering audios/bubbles overlap
    for f in os.listdir("."):
        if (f.startswith("audio_") and f.endswith(".mp3")) or \
           (f.startswith("bubble_") and f.endswith(".png")) or \
           (f.startswith("caption_") and f.endswith(".png")) or \
           (f.startswith("final_part") and f.endswith(".mp4")):
            try:
                os.remove(f)
            except:
                pass
                
    # Execute Video Assembly
    run_script("chat_generator.py")
    
    # Execute YouTube Push
    run_script("youtube_uploader.py")
    
    print("\n>>> Pipeline Execution Officially Complete! <<<")

if __name__ == "__main__":
    main()
