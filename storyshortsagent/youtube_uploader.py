import os
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def resolve_file_path(target, fallbacks):
    candidates = [target] + fallbacks
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return target

def get_youtube_service(client_secrets_file='client_secrets.json', token_file='token.json'):
    resolved_token_file = resolve_file_path(
        token_file,
        [
            'token.json',
            'token.pickle',
            os.path.join('..', 'token.json'),
            os.path.join('..', 'token.pickle'),
            os.path.join('..', 'gametraileragent', 'token.json')
        ]
    )

    resolved_secrets_file = resolve_file_path(
        client_secrets_file,
        [
            'client_secrets.json',
            os.path.join('..', 'client_secrets.json'),
            os.path.join('..', 'gametraileragent', 'client_secrets.json')
        ]
    )

    creds = None
    if os.path.exists(resolved_token_file):
        try:
            creds = Credentials.from_authorized_user_file(resolved_token_file, SCOPES)
        except Exception:
            import pickle
            try:
                with open(resolved_token_file, "rb") as f:
                    creds = pickle.load(f)
            except Exception as e:
                print(f"Error loading credentials from {resolved_token_file}: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(resolved_secrets_file):
                print(f"Error: {client_secrets_file} not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(resolved_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        target_save = resolved_token_file if os.path.exists(resolved_token_file) else token_file
        try:
            with open(target_save, 'w') as token:
                token.write(creds.to_json())
        except Exception:
            pass

    return build('youtube', 'v3', credentials=creds)

def upload_to_youtube(video_path, title, description, tags=None, category_id="22",
                      thumbnail_path=None,
                      client_secrets_file='client_secrets.json',
                      token_file='token.json'):
    youtube = get_youtube_service(client_secrets_file, token_file)
    if not youtube:
        return None

    print(f"Uploading {video_path} to YouTube Shorts (Chat Stories channel)...")
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or [],
            'categoryId': category_id  # 22 = People & Blogs (fits story content)
        },
        'status': {
            'privacyStatus': 'public',
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
            print(f"  Uploaded {int(status.progress() * 100)}%")

    video_id = response['id']
    print(f"Upload Complete! Video ID: {video_id}")
    print(f"Watch: https://youtube.com/shorts/{video_id}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("Thumbnail uploaded.")
        except Exception as e:
            print(f"Thumbnail upload failed: {e}")

    return video_id


if __name__ == "__main__":
    upload_to_youtube("output/test.mp4", "Test Story Short #Shorts", "Test upload")
