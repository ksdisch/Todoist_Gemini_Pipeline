import google.generativeai as genai
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set.")

class GeminiClient:
    def __init__(self, model_name=None, system_prompt=None):
        # Use configured model or default if not provided
        self.model_name = model_name or GEMINI_MODEL
        self.system_prompt = system_prompt
        self.model = self._initialize_model()
        self.chat_session = None

    def _initialize_model(self):
        """Initializes the model, validating it and falling back if necessary."""
        if not GEMINI_API_KEY:
             # If no key, we can't validate, just return the requested model wrapper
             # Errors will happen at runtime effectively.
             return genai.GenerativeModel(self.model_name)

        try:
            return self._get_validated_model(self.model_name)
        except Exception as e:
            logger.error(f"Error initializing model '{self.model_name}': {e}")
            fallback_model = "models/gemini-flash-latest"
            if self.model_name != fallback_model:
                logger.warning(f"Falling back to default model: {fallback_model}")
                return genai.GenerativeModel(fallback_model)
            else:
                 # If we were already trying the fallback and it failed, re-raise or return it anyway
                 raise e

    def _get_validated_model(self, model_name):
        """Checks if model exists and supports generateContent. Returns GenerativeModel."""
        # Simple check: try to list models and find it.
        try:
             # We iterate to find a match.
             # This might be slow if there are many models, but it's a one-time startup check.
             all_models = list(genai.list_models())
             target_names = [model_name, f"models/{model_name}"] if not model_name.startswith("models/") else [model_name]
             
             for m in all_models:
                 if m.name in target_names:
                     if "generateContent" in m.supported_generation_methods:
                        return genai.GenerativeModel(model_name)
                     else:
                        raise ValueError(f"Model {model_name} found but does not support generateContent.")
             
             # If we get here, model not found in list
             raise ValueError(f"Model {model_name} not found in available models.")

        except Exception as e:
            # If list_models fails or we raised above, propagate to trigger fallback
            raise e

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
