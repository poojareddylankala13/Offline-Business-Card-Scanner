import bcrypt
import re

def hash_password(password: str) -> str:
    """
    Hashes a password using bcrypt and returns the decoded string.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a plain text password against a bcrypt hash.
    """
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

def sanitize_input(text: str) -> str:
    """
    Sanitizes string inputs to prevent basic scripting or tag injections.
    """
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]*>', '', text)
    # Basic strip
    return clean.strip()
