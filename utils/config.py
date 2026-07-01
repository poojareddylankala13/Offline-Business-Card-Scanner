import os
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from utils.logger import get_logger

# Load environmental variables
load_dotenv()

logger = get_logger("config")

# Project base path (workspace root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Configurations & Paths
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"))
MODEL_URL = os.getenv("MODEL_URL", "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "database" / "contacts.db"))
UPLOADS_DIR = os.getenv("UPLOADS_DIR", str(BASE_DIR / "uploads"))
CACHE_DIR = os.getenv("CACHE_DIR", str(BASE_DIR / "cache"))
LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO")

# Map string representation of log level to logging constants
import logging
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}
LOG_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL_STR.upper(), logging.INFO)

# Make sure all directories exist
for directory in [os.path.dirname(MODEL_PATH), os.path.dirname(DATABASE_PATH), UPLOADS_DIR, CACHE_DIR, LOG_DIR]:
    if directory:
        os.makedirs(directory, exist_ok=True)

# Register Tesseract Command Path if specified
import pytesseract
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    logger.info(f"Tesseract executable set to: {TESSERACT_CMD}")
else:
    logger.warning(f"Configured Tesseract path does not exist: {TESSERACT_CMD}. App will fall back to system PATH for 'tesseract'.")

def get_tesseract_status() -> bool:
    """
    Checks if Tesseract is available either at the configured path or in system PATH.
    """
    if os.path.exists(TESSERACT_CMD):
        return True
    # Try calling tesseract version to see if it is in system path
    import subprocess
    try:
        subprocess.run(["tesseract", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def check_model_exists() -> bool:
    """
    Returns true if the GGUF model exists at the configured path and is non-empty.
    """
    path = Path(MODEL_PATH)
    return path.exists() and path.stat().st_size > 10 * 1024 * 1024  # greater than 10MB

def download_model(progress_callback=None) -> bool:
    """
    Downloads the TinyLlama model to the configured path.
    progress_callback is a function receiving (bytes_downloaded, total_bytes).
    """
    dest_path = Path(MODEL_PATH)
    os.makedirs(dest_path.parent, exist_ok=True)
    
    logger.info(f"Starting download of TinyLlama model from {MODEL_URL} to {MODEL_PATH}")
    
    try:
        # Request headers to download from HuggingFace
        req = urllib.request.Request(
            MODEL_URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            block_size = 1024 * 1024  # 1MB blocks
            downloaded = 0
            
            with open(dest_path, 'wb') as out_file:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
                        
        logger.info("TinyLlama model download completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to download TinyLlama model: {e}")
        if dest_path.exists():
            try:
                dest_path.unlink()  # clean up incomplete file
            except Exception:
                pass
        return False
