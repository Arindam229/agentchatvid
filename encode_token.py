import base64
import os

print("\n=======================================================")
print("         GITHUB ACTIONS SECRETS GENERATOR")
print("=======================================================\n")

def print_secret(title, secret_name, paths):
    found_path = None
    for p in paths:
        if os.path.exists(p):
            found_path = p
            break
    if found_path:
        with open(found_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        print(f"[+] Loaded from: {found_path}")
        print(f">>> Secret Name: {secret_name}")
        print(encoded)
        print("\n-------------------------------------------------------\n")
    else:
        print(f"[-] No file found for {secret_name} in {paths}\n")

# 1. Main Shared YouTube Token
print_secret(
    "Main YouTube Token",
    "YOUTUBE_TOKEN_BASE64",
    ["token.pickle", "token.json", os.path.join("storyshortsagent", "token.json")]
)

# 2. GameTrailers YouTube Token (if dedicated channel)
print_secret(
    "Game Trailers YouTube Token",
    "GAMETRAILERS_TOKEN_BASE64",
    [
        os.path.join("gametraileragent", "token.json"),
        os.path.join("gametraileragent", "token.pickle")
    ]
)

print("Copy the values above and add them as secrets in GitHub Repository Settings.")
