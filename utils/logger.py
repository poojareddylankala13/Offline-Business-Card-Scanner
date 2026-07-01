import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(log_dir="logs", log_level=logging.INFO):
    """
    Sets up the logging system, writing to both logs/app.log and console.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    log_file_path = os.path.join(log_dir, "app.log")
    
    # Configure formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Root logger config
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to prevent duplicate logging
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # File handler (with rotation: max 5MB, keeping 3 backup files)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info(f"Logger initialized. Writing to {log_file_path}")

def get_logger(name):
    """
    Returns a configured logger with the given name.
    """
    return logging.getLogger(name)
