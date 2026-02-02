import json
import re

def extract_first_json(text: str):
    """
    Finds and parses the first valid JSON object in the text.
    Uses json.JSONDecoder.raw_decode to handle trailing text/markdown.
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
    return None
