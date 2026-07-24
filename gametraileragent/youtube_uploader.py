import os
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_youtube_service(client_secrets_file='client_secrets.json', token_file='token.json'):
    creds = None
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception:
            import pickle
            try:
                with open(token_file, "rb") as f:
                    creds = pickle.load(f)
            except Exception as e:
                print(f"Error loading credentials from {token_file}: {e}")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_file):
                print(f"Error: {client_secrets_file} not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return build('youtube', 'v3', credentials=creds)

def upload_to_youtube(video_path, title, description, tags=None, category_id="20", thumbnail_path=None, client_secrets_file='client_secrets.json', token_file='token.json'): # 20 is Gaming
    youtube = get_youtube_service(client_secrets_file, token_file)
    if not youtube:
        return False

    print(f"Uploading {video_path} to YouTube Shorts...")
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public', # User explicitly requested public uploads
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"Upload Complete! Video ID: {response['id']}")
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        print(f"Uploading thumbnail: {thumbnail_path}")
        try:
            youtube.thumbnails().set(
                videoId=response['id'],
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("Thumbnail uploaded successfully!")
        except Exception as e:
            print(f"Failed to upload thumbnail: {e}")
            
    return response['id']

if __name__ == "__main__":
    upload_to_youtube("short_1.mp4", "Test Short #Shorts", "This is a test upload for YouTube Shorts")
