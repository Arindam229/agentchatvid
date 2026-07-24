import base64
import os

token_file = "token.pickle"
if os.path.exists(token_file):
    with open(token_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    print("\n=======================================================")
    print("      YOUR YOUTUBE_TOKEN_BASE64 SECRET STRING")
    print("=======================================================\n")
    print(encoded)
    print("\n=======================================================")
    print("Copy the text above and paste it into GitHub Secret named: YOUTUBE_TOKEN_BASE64")
    print("=======================================================\n")
else:
    print(f"Error: {token_file} not found in the current directory.")
