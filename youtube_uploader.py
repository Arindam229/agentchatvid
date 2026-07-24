import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

import pickle
from google.auth.transport.requests import Request

scopes = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_service():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    api_service_name = "youtube"
    api_version = "v3"
    client_secrets_file = "client_secrets.json"
    token_file = "token.pickle"
    
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_file):
                print(f"ERROR: {client_secrets_file} not found. Please download OAuth 2.0 Credentials from Google Cloud Console.")
                exit(1)
            print("Authenticating with Google OAuth...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, scopes)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)
    
    return googleapiclient.discovery.build(
        api_service_name, api_version, credentials=creds)

def upload_video(youtube, file_path, part_index=None, total_parts=None, ai_title=None, ai_description=None):
    title = ai_title if ai_title else "Crazy Text Story #shorts"
    description = ai_description if ai_description else "Auto-Generated Text Story! #shorts #texts"

    if part_index is not None and total_parts is not None and total_parts > 1:
        title = f"{title} (Part {part_index})"

    print(f"Starting Upload for {file_path} - Title: {title}")
    request = youtube.videos().insert(
        part="snippet,status",
        body={
          "snippet": {
            "categoryId": "24", # Entertainment
            "description": description,
            "title": title
          },
          "status": {
            "privacyStatus": "public"
          }
        },
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
    )
    
    response = request.execute()
    print(f"Upload successful! Video ID: {response.get('id')}")

if __name__ == "__main__":
    import glob
    import json
    # Look for segmented parts first
    video_files = sorted(glob.glob("final_part*.mp4"), key=lambda x: int(x.split("part")[-1].split(".")[0]))
    
    # Fallback to single file if no parts found
    if not video_files and os.path.exists("final.mp4"):
        video_files = ["final.mp4"]
        
    if not video_files:
        print("No video files (final.mp4 or final_part*.mp4) found. Pipeline failure.")
        exit(1)

    ai_title = None
    ai_description = None
    if os.path.exists("input.json"):
        try:
            with open("input.json", "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    ai_title = data.get("video_title")
                    ai_description = data.get("video_description")
        except:
            pass

    youtube_service = get_authenticated_service()
    
    for i, file_path in enumerate(video_files):
        upload_video(youtube_service, file_path, 
                     part_index=i+1, 
                     total_parts=len(video_files), 
                     ai_title=ai_title, 
                     ai_description=ai_description)
        
    print("\nAll uploads finished.")
