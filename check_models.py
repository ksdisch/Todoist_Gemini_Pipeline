import google.generativeai as genai
import os

# Use the key from the user's file (hardcoded for this check as we know it from the diff)
GEMINI_API_KEY = "AIzaSyDHOk3nmfZUlPXFdLNiqpDbXIck3Tdlrtk"
genai.configure(api_key=GEMINI_API_KEY)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
