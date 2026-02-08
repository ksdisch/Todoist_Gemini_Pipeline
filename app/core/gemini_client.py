import google.generativeai as genai
from app.core.config import GEMINI_API_KEY
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set.")

class GeminiClient:
    def __init__(self, model_name='gemini-1.5-flash-latest', system_prompt=None):
        # We don't raise here to allow the app to launch even if config is missing.
        # Errors will be caught when trying to use the client.
        self.model = genai.GenerativeModel(model_name)
        self.chat_session = None
        self.system_prompt = system_prompt

    def start_chat(self, history=None):
        """Starts a new chat session."""
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY is not set. Please check your .env file.")
             
        self.chat_session = self.model.start_chat(history=history or [])
        return self.chat_session

    def send_message(self, message):
        """Sends a message to the chat session."""
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY is not set. Please check your .env file.")

        if not self.chat_session:
            self.start_chat()
        try:
            response = self.chat_session.send_message(message)
            if not response.text:
                raise ValueError("Gemini returned an empty response.")
            return response.text
        except Exception as e:
            logger.error(f"Error sending message to Gemini: {e}")
            raise e # Re-raise to let the caller (and UI) handle the specific error
