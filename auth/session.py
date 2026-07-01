import streamlit as st
import time
from typing import Optional, Dict, Any

SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 minutes session timeout

def init_session():
    """
    Initializes Streamlit session state variables if they are not already set.
    """
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "recent_searches" not in st.session_state:
        st.session_state["recent_searches"] = []
    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = time.time()
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Login"

def check_session_timeout() -> bool:
    """
    Checks if the session has timed out due to inactivity.
    If timed out, logs the user out and returns True.
    """
    init_session()
    if not st.session_state["authenticated"]:
        return False
        
    now = time.time()
    elapsed = now - st.session_state.get("last_activity", now)
    
    if elapsed > SESSION_TIMEOUT_SECONDS:
        logout_user()
        st.warning("Session expired due to inactivity. Please log in again.")
        logger = get_logger_fallback()
        logger.info("Session timed out.")
        return True
        
    st.session_state["last_activity"] = now
    return False

def login_user(user_data: Dict[str, Any]):
    """
    Sets the user data in the session state.
    """
    init_session()
    st.session_state["authenticated"] = True
    st.session_state["user"] = {
        "id": user_data["id"],
        "full_name": user_data["full_name"],
        "username": user_data["username"],
        "email": user_data["email"]
    }
    st.session_state["last_activity"] = time.time()
    st.session_state["current_page"] = "Dashboard"

def logout_user():
    """
    Clears all session variables.
    """
    init_session()
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["recent_searches"] = []
    st.session_state["current_page"] = "Login"

def is_logged_in() -> bool:
    """
    Returns True if a user is logged in and authenticated.
    """
    init_session()
    return st.session_state["authenticated"]

def add_recent_search(query: str):
    """
    Adds a query to the recent search queries list (max 5 items, duplicates removed).
    """
    init_session()
    q = query.strip()
    if not q:
        return
    history = st.session_state["recent_searches"]
    if q in history:
        history.remove(q)
    history.insert(0, q)
    st.session_state["recent_searches"] = history[:5]

def get_logger_fallback():
    try:
        from utils.logger import get_logger
        return get_logger("session")
    except Exception:
        import logging
        return logging.getLogger("session")
