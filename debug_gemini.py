from app.core.gemini_client import GeminiClient
import logging
import sys

# Configure basic logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

print("--- Starting Gemini Debug ---")
try:
    client = GeminiClient()
    print("Client initialized.")
    
    print("Sending message: 'Hello'")
    response = client.send_message("Hello")
    
    if response:
        print(f"Response Received: {response}")
    else:
        print("Response was None or empty.")

except Exception as e:
    print(f"Exception occurred: {e}")

print("--- End Gemini Debug ---")
