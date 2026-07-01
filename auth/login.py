import streamlit as st
from db.sqlite_db import get_user_by_username
from auth.security import verify_password, sanitize_input
from auth.session import login_user

def render_login():
    """
    Renders the Login Form in Streamlit.
    """
    st.markdown("<h2 style='text-align: center;'>🔐 Sign In to Scanner</h2>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username:", placeholder="Enter your username")
        password = st.text_input("Password:", type="password", placeholder="Enter your password")
        
        submit_btn = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        
        if submit_btn:
            s_username = sanitize_input(username)
            
            if not s_username or not password:
                st.error("⚠️ Username and password are required.")
                return
                
            # Retrieve user
            user = get_user_by_username(s_username)
            
            if user:
                # Verify password
                if verify_password(password, user["password_hash"]):
                    # Success
                    st.success("🔓 Authenticated!")
                    login_user(user)
                    st.rerun()
                else:
                    st.error("⚠️ Invalid username or password.")
            else:
                st.error("⚠️ Invalid username or password.")
