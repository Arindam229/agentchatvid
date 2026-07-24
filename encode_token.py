import base64
import os

print("\n=======================================================")
print("         GITHUB ACTIONS SECRETS GENERATOR")
print("=======================================================\n")

token_found = False

# Try token.pickle first, fallback to token.json
if os.path.exists("token.pickle"):
    token_path = "token.pickle"
elif os.path.exists(os.path.join("storyshortsagent", "token.json")):
    token_path = os.path.join("storyshortsagent", "token.json")
elif os.path.exists("token.json"):
    token_path = "token.json"
else:
    token_path = None

if token_path:
    with open(token_path, "rb") as f:
        encoded_token = base64.b64encode(f.read()).decode("utf-8")
    print(f"[+] Loaded credentials from: {token_path}")
    print("\n>>> YOUTUBE_TOKEN_BASE64 Secret String:")
    print(encoded_token)
    print("\n=======================================================")
    print("Copy the string above and paste it into GitHub Secret named: YOUTUBE_TOKEN_BASE64")
    print("This single token will authorize uploads for BOTH pipelines!")
    print("=======================================================\n")
else:
    print("[-] Error: No token file (token.pickle or token.json) found.")
