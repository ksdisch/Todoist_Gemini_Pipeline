import json
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# =================================================================================================
# TOUR HEADER: Parser
# =================================================================================================
#
# JOB: 
# This module is responsible for extracting structured data (JSON) from the messy natural language
# output of the LLM. It acts as a filter/sanitizer.
#
# THE PROBLEM:
# LLMs often wrap JSON in markdown (```json ... ```) or add polite conversational text 
# ("Here is your plan: ..."). A standard json.loads() will fail on this extra text.
#
# STRATEGY:
# instead of trying to use regex to clean the string, we use the property that JSON objects start 
# with '{'. We find the first '{' and use the JSON decoder's ability to stop reading once the 
# valid object ends.
#
# =================================================================================================

def extract_first_json(text: str):
    """
    Finds and parses the first valid JSON object in the text.
    
    Why Raw Decode?
    - json.JSONDecoder.raw_decode() is powerful because it returns the parsed object AND the index where it stopped.
    - This allows us to ignore any "postamble" text (e.g. "Let me know if you need changes").
    - We manually find the start index to ignore "preamble" text.
    """
    if not text:
        return None
        
    # Locate the first opening brace
    start_idx = text.find('{')
    if start_idx == -1:
        return None
        
    try:
        # raw_decode parses a valid JSON document from the start index 
        # and returns the object and the end index.
        parsed_obj, _ = json.JSONDecoder().raw_decode(text, idx=start_idx)
        return parsed_obj
    except json.JSONDecodeError:
        return None

def validate_schema(data):
    """
    Validates the parsed data against the required schema:
    {
        "thought": str,
        "actions": list
    }
    """
    if not isinstance(data, dict):
        return False
        
    # Check 'thought' field
    if "thought" not in data or not isinstance(data["thought"], str):
        return False
        
    # Check 'actions' field
    if "actions" not in data or not isinstance(data["actions"], list):
        return False
        
    return True

def parse_and_validate_response(text: str):
    """
    Main entry point for parsing AI responses.
    
    1. Extracts strict JSON object.
    2. Validates against schema.
    
    Returns the valid dict, or None if parsing/validation fails.
    """
    data = extract_first_json(text)
    if data and validate_schema(data):
        return data
    
    logger.warning("Failed to parse or validate AI response")
    return None
