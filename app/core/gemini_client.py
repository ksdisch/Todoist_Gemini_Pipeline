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
        self.model = genai.GenerativeModel(model_name)
        self.chat_session = None
        self.system_prompt = system_prompt

    def start_chat(self, history=None):
        """Starts a new chat session."""
        initial_history = []
        if self.system_prompt:
             # This is a bit of a hack as Gemini header handling differs by library version,
             # but often sending system prompt as first user message works.
             # Alternatively, use system_instruction in GenerativeModel constructor if supported.
             # For now, following the pattern in todo_analyst.py
             pass
        
        # In the original code, history was passed to start_chat.
        self.chat_session = self.model.start_chat(history=history or [])
        return self.chat_session

    def send_message(self, message):
        """Sends a message to the chat session."""
        if not self.chat_session:
            self.start_chat()
        try:
            response = self.chat_session.send_message(message)
            return response.text
        except Exception as e:
            logger.error(f"Error sending message to Gemini: {e}")
            return None
