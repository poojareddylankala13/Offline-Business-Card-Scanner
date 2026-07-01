import json
import re
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, ValidationError
from utils.logger import get_logger

logger = get_logger("validators")

class BusinessCardInfo(BaseModel):
    name: str = Field(default="", description="Full name of the contact person")
    designation: str = Field(default="", description="Job title or designation")
    company: str = Field(default="", description="Name of the company or organization")
    phone: str = Field(default="", description="Phone number(s)")
    email: str = Field(default="", description="Email address(es)")
    website: str = Field(default="", description="Website URL")
    address: str = Field(default="", description="Physical address or location")

    def to_dict(self) -> Dict[str, str]:
        return self.model_dump()

REQUIRED_KEYS = {"name", "designation", "company", "phone", "email", "website", "address"}

def extract_json_block(text: str) -> str:
    """
    Finds and extracts a JSON block from freeform text.
    Handles Markdown backticks and basic text wrapping.
    """
    # Try to find ```json ... ``` blocks
    json_code_block_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if json_code_block_match:
        return json_code_block_match.group(1).strip()
        
    # Try to find ``` ... ``` blocks
    code_block_match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Find the first occurrences of '{' and matching last '}'
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1].strip()
        
    return text.strip()

def sanitize_json_string(json_str: str) -> str:
    """
    Performs basic regex-based sanitization to fix common LLM JSON syntax errors.
    """
    # Remove trailing commas before closing braces/brackets
    # e.g., "key": "value", } -> "key": "value" }
    json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
    
    # Fix control characters (replace real newlines inside JSON values with \n)
    # Simple strategy: keep newlines only outside quotes, replace inside quotes.
    # For now, we will do a basic replacement of raw tabs with \t.
    json_str = json_str.replace('\t', '\\t')
    
    # Fix unquoted key names or single quoted values
    # TinyLlama might use single quotes instead of double quotes
    # Replace single quotes with double quotes, but be careful with single quotes inside words.
    # To be safe, we only replace single quotes that are used as string delimiters:
    # Match single quote at start/end of string, or around keys
    # Let's do a simple replace of single quotes with double quotes only if they border syntax delimiters
    # or just try a basic replacement if double quotes are missing entirely.
    if '"' not in json_str and "'" in json_str:
        logger.warning("JSON appears to use single quotes instead of double quotes. Attempting to convert.")
        json_str = json_str.replace("'", '"')
        
    return json_str

def validate_and_correct_json(raw_output: str) -> Tuple[bool, Dict[str, str], str]:
    """
    Parses, validates and corrects JSON from LLM output.
    Returns (success, parsed_dict, error_message).
    """
    clean_str = extract_json_block(raw_output)
    
    try:
        # Attempt 1: Direct JSON parsing
        parsed = json.loads(clean_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parse failed: {e}. Attempting auto-correction.")
        # Attempt 2: Auto-correction
        try:
            corrected_str = sanitize_json_string(clean_str)
            parsed = json.loads(corrected_str)
        except json.JSONDecodeError as e2:
            msg = f"Failed to parse LLM output as JSON. Original error: {e}. Corrected error: {e2}"
            logger.error(msg)
            return False, {}, msg

    if not isinstance(parsed, dict):
        return False, {}, "Parsed JSON is not an object/dictionary."

    # Fill in missing fields with empty strings, and ensure all values are strings
    standardized = {}
    for key in REQUIRED_KEYS:
        val = parsed.get(key, "")
        if val is None:
            standardized[key] = ""
        elif isinstance(val, (dict, list)):
            standardized[key] = json.dumps(val)
        else:
            standardized[key] = str(val).strip()
            
    # Validate against Pydantic schema
    try:
        validated_model = BusinessCardInfo(**standardized)
        logger.info("JSON successfully validated against Pydantic schema.")
        return True, validated_model.to_dict(), ""
    except ValidationError as ve:
        msg = f"Pydantic validation failed: {ve}"
        logger.error(msg)
        return False, {}, msg
