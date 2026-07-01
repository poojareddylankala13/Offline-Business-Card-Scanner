import streamlit as st
import re
from db.sqlite_db import create_user, get_user_by_username, get_user_by_email, DuplicateUserError
from auth.security import hash_password, sanitize_input
from auth.session import login_user

def render_register():
    """
    Renders the Registration Form in Streamlit.
    """
    st.markdown("<h2 style='text-align: center;'>📝 Create Local Account</h2>", unsafe_allow_html=True)
    
    with st.form("register_form"):
        full_name = st.text_input("Full Name:", placeholder="e.g. John Doe")
        username = st.text_input("Username:", placeholder="e.g. johndoe")
        email = st.text_input("Email Address:", placeholder="e.g. john.doe@company.com")
        password = st.text_input("Password:", type="password", placeholder="Minimum 6 characters")
        confirm_password = st.text_input("Confirm Password:", type="password", placeholder="Repeat your password")
        
        submit_btn = st.form_submit_button("Sign Up", type="primary", use_container_width=True)
        
        if submit_btn:
            # Inputs sanitization
            s_full_name = sanitize_input(full_name)
            s_username = sanitize_input(username)
            s_email = sanitize_input(email)
            
            # Validation
            if not s_full_name or not s_username or not s_email or not password or not confirm_password:
                st.error("⚠️ All fields are required.")
                return
                
            if len(s_username) < 3:
                st.error("⚠️ Username must be at least 3 characters long.")
                return
                
            # Email regex validation
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, s_email):
                st.error("⚠️ Please enter a valid email address.")
                return
                
            if len(password) < 6:
                st.error("⚠️ Password must be at least 6 characters long.")
                return
                
            if password != confirm_password:
                st.error("⚠️ Passwords do not match.")
                return
                
            # Process registration
            try:
                # Hash the password securely
                pwd_hash = hash_password(password)
                
                # Insert user into database
                user_id = create_user(
                    full_name=s_full_name,
                    username=s_username,
                    email=s_email,
                    password_hash=pwd_hash
                )
                
                st.success("🎉 Account created successfully!")
                
                # Get the created user object for session logging
                user_data = {
                    "id": user_id,
                    "full_name": s_full_name,
                    "username": s_username,
                    "email": s_email
                }
                
                # Automatically login
                login_user(user_data)
                
                # Success notification and re-run
                st.toast("Welcome! Logging you in automatically...")
                st.rerun()
                
            except DuplicateUserError as e:
                st.error(f"⚠️ Registration error: {e}")
            except Exception as e:
                st.error(f"⚠️ System error occurred during registration. Check logs.")
