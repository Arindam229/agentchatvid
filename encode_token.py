import base64
import os

print("\n=======================================================")
print("         GITHUB ACTIONS SECRETS GENERATOR")
print("=======================================================\n")

# 1. Chat Vid Token (token.pickle)
token_pickle = "token.pickle"
if os.path.exists(token_pickle):
    with open(token_pickle, "rb") as f:
        encoded_pickle = base64.b64encode(f.read()).decode("utf-8")
    print(">>> YOUTUBE_TOKEN_BASE64 (for Chat Vid agent):")
    print(encoded_pickle)
    print("\n-------------------------------------------------------\n")
else:
    print("[-] token.pickle not found in root directory.\n")

# 2. StoryShorts Token (storyshortsagent/token.json)
token_json = os.path.join("storyshortsagent", "token.json")
if not os.path.exists(token_json) and os.path.exists("token.json"):
    token_json = "token.json"

if os.path.exists(token_json):
    with open(token_json, "rb") as f:
        encoded_json = base64.b64encode(f.read()).decode("utf-8")
    print(">>> STORYSHORTS_TOKEN_BASE64 (for StoryShorts agent):")
    print(encoded_json)
    print("\n-------------------------------------------------------\n")
else:
    print("[-] token.json not found in storyshortsagent/ directory.\n")

print("Copy the values above and add them as secrets in your GitHub Repository Settings.")
