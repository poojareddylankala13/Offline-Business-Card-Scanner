import os
import re
import json
import psutil
from typing import Dict, Any, Tuple, Optional
from llama_cpp import Llama
from utils.config import MODEL_PATH, check_model_exists
from utils.logger import get_logger
from utils.validators import validate_and_correct_json

logger = get_logger("parser")

# Global model instance for reuse (lazy initialized)
_llm_instance: Optional[Llama] = None

def get_llm() -> Llama:
    """
    Lazy initializes and returns the Llama instance.
    Raises FileNotFoundError if model file does not exist.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance
        
    if not check_model_exists():
        logger.error(f"Model file not found at: {MODEL_PATH}")
        raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}. Please download it first.")
        
    logger.info(f"Loading local LLM model from: {MODEL_PATH}")
    
    # Determine optimal number of CPU threads (usually physical cores)
    physical_cores = psutil.cpu_count(logical=False)
    threads = max(2, physical_cores) if physical_cores else 4
    logger.info(f"Setting llama.cpp thread count to: {threads}")
    
    try:
        # Load model on CPU
        _llm_instance = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,           # 2048 context length is plenty for business cards
            n_threads=threads,
            verbose=False,        # Disable verbose output to keep logs clean
            n_gpu_layers=0        # Force CPU execution
        )
        logger.info("Local LLM model loaded successfully.")
        return _llm_instance
    except Exception as e:
        logger.error(f"Failed to load Llama model: {e}")
        raise RuntimeError(f"Failed to load local Small Language Model: {e}")

def regex_fallback_extractor(ocr_text: str) -> Dict[str, str]:
    """
    Heuristical regex extractor to pull basic details from raw OCR text
    in case the LLM fails or is not available.
    """
    logger.info("Running heuristical regex-based fallback extraction.")
    result = {
        "name": "",
        "designation": "",
        "company": "",
        "phone": "",
        "email": "",
        "website": "",
        "address": ""
    }
    
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    if not lines:
        return result
        
    # Email matching
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = []
    # Website matching
    web_pattern = r'(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+\.(?:com|org|net|co|in|io|info|biz|me|cc|us|ca|uk|in|gov|edu|tech|xyz)'
    websites = []
    # Phone matching (looking for patterns like +1-234-567-8900, 0123-456789, etc.)
    phone_pattern = r'\+?\(?\d{1,4}\)?(?:[-.\s/]?\(?\d{1,6}\)?){1,4}'
    phones = []
    
    for line in lines:
        # Extract emails
        found_emails = re.findall(email_pattern, line)
        if found_emails:
            emails.extend(found_emails)
            
        # Extract websites (excluding emails matching the same website domains)
        found_webs = re.findall(web_pattern, line)
        for w in found_webs:
            if "@" not in w and not any(w in email for email in emails):
                websites.append(w)
                
        # Extract phone numbers
        found_phones = re.findall(phone_pattern, line)
        if found_phones:
            for p in found_phones:
                p_clean = p.strip()
                # Count actual digits to filter out zip codes or addresses
                digit_count = sum(c.isdigit() for c in p_clean)
                if digit_count >= 7:
                    phones.append(p_clean)

    if emails:
        result["email"] = ", ".join(list(dict.fromkeys(emails)))
    if websites:
        result["website"] = ", ".join(list(dict.fromkeys(websites)))
    if phones:
        result["phone"] = ", ".join(list(dict.fromkeys(phones)))

    # Basic Heuristics for Name, Company, Title:
    # Usually: Line 0 is Name or Company
    # Line 1 is Title/Designation
    # If the first line doesn't look like a website/email/phone, assign it to name/company
    non_contact_lines = []
    for line in lines:
        # Skip lines that contain contact details we already extracted
        if any(e in line for e in emails) or any(w in line for w in websites) or any(p in line for p in phones):
            continue
        # Skip lines containing typical keywords
        if any(kw in line.lower() for kw in ["phone", "tel", "cell", "fax", "email", "mail", "web", "http", "www", "address", "street", "road"]):
            continue
        non_contact_lines.append(line)

    if len(non_contact_lines) > 0:
        result["name"] = non_contact_lines[0]
    if len(non_contact_lines) > 1:
        result["designation"] = non_contact_lines[1]
    if len(non_contact_lines) > 2:
        result["company"] = non_contact_lines[2]
    if len(non_contact_lines) > 3:
        result["address"] = ", ".join(non_contact_lines[3:])
        
    return result

def extract_structured_data(ocr_text: str) -> Tuple[Dict[str, str], bool]:
    """
    Uses the local TinyLlama model to extract structured data from OCR text.
    Returns (structured_data, used_llm).
    If LLM loading or parsing fails, falls back to regex-based extraction.
    """
    # If model doesn't exist, execute regex fallback immediately
    if not check_model_exists():
        logger.warning("Local GGUF model is not present. Falling back to regex extraction.")
        return regex_fallback_extractor(ocr_text), False

    try:
        llm = get_llm()
    except Exception as e:
        logger.error(f"Could not load LLM model. Falling back to regex. Error: {e}")
        return regex_fallback_extractor(ocr_text), False

    logger.info("Preparing prompt for TinyLlama.")
    
    # Construct a structured prompt for ChatML or standard instruction format.
    # TinyLlama 1.1B Chat uses:
    # <|system|>
    # system message</s>
    # <|user|>
    # user message</s>
    # <|assistant|>
    
    prompt = (
        "<|system|>\n"
        "You are a precise business card information extractor. You MUST output ONLY a valid JSON object matching the schema. Do not add any conversational text or comments.\n"
        "If a field cannot be found, fill it with \"\".\n"
        "Required JSON Schema:\n"
        "{\n"
        "  \"name\": \"\",\n"
        "  \"designation\": \"\",\n"
        "  \"company\": \"\",\n"
        "  \"phone\": \"\",\n"
        "  \"email\": \"\",\n"
        "  \"website\": \"\",\n"
        "  \"address\": \"\"\n"
        "}\n"
        "</s>\n"
        "<|user|>\n"
        f"Extract information from this OCR text:\n"
        f"\"\"\"\n{ocr_text}\n\"\"\"\n"
        "</s>\n"
        "<|assistant|>\n"
    )

    logger.info("Running llama.cpp local inference.")
    try:
        response = llm(
            prompt,
            max_tokens=400,
            temperature=0.1,  # Low temperature for deterministic extraction
            stop=["</s>", "<|user|>"],
            echo=False
        )
        
        raw_output = response["choices"][0]["text"].strip()
        logger.info(f"Raw LLM output: {raw_output}")
        
        # Validate and correct
        success, structured_json, err = validate_and_correct_json(raw_output)
        if success:
            return structured_json, True
        else:
            logger.warning(f"LLM produced invalid JSON structure: {err}. Retrying LLM inference once.")
            # Retry once with a slightly more explicit request
            retry_prompt = prompt + raw_output + "\n\nError: Invalid JSON. Please fix it and output ONLY valid JSON matching the schema."
            response = llm(retry_prompt, max_tokens=400, temperature=0.1, stop=["</s>"], echo=False)
            retry_raw = response["choices"][0]["text"].strip()
            success_retry, structured_json_retry, err_retry = validate_and_correct_json(retry_raw)
            if success_retry:
                logger.info("JSON successfully parsed on retry.")
                return structured_json_retry, True
                
            # If retry also fails, fall back to regex
            logger.error(f"LLM retry failed: {err_retry}. Falling back to regex.")
            return regex_fallback_extractor(ocr_text), False
            
    except Exception as e:
        logger.error(f"Inference error: {e}. Falling back to regex.")
        return regex_fallback_extractor(ocr_text), False
