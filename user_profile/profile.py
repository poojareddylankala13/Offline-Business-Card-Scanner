import streamlit as st
import re
from db.sqlite_db import get_user_by_id, get_user_stats, update_user_profile, update_user_password, DuplicateUserError
from auth.security import verify_password, hash_password, sanitize_input

def render_profile(user_id: int):
    """
    Renders the Profile settings page.
    """
    st.markdown("<h2>👤 User Profile Management</h2>", unsafe_allow_html=True)
    
    # Fetch fresh user details
    user = get_user_by_id(user_id)
    if not user:
        st.error("Error retrieving user details.")
        return
        
    stats = get_user_stats(user_id)
    
    col_details, col_form = st.columns([1, 1.2])
    
    with col_details:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 📋 Account Details")
        st.markdown(f"**Full Name:** {user['full_name']}")
        st.markdown(f"**Username:** {user['username']}")
        st.markdown(f"**Email:** {user['email']}")
        st.markdown(f"**Member Since:** {user['created_at']}")
        st.markdown(f"**Total Business Cards Scanned:** `{stats['total_cards']}`")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Change Password Form
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 🔑 Change Password")
        with st.form("password_form"):
            curr_pass = st.text_input("Current Password:", type="password")
            new_pass = st.text_input("New Password:", type="password", placeholder="Minimum 6 characters")
            confirm_new_pass = st.text_input("Confirm New Password:", type="password")
            
            pass_submit = st.form_submit_button("Update Password", type="primary", use_container_width=True)
            
            if pass_submit:
                if not curr_pass or not new_pass or not confirm_new_pass:
                    st.error("⚠️ All password fields are required.")
                elif not verify_password(curr_pass, user["password_hash"]):
                    st.error("⚠️ Incorrect current password.")
                elif len(new_pass) < 6:
                    st.error("⚠️ New password must be at least 6 characters.")
                elif new_pass != confirm_new_pass:
                    st.error("⚠️ Confirm password does not match new password.")
                else:
                    try:
                        new_hash = hash_password(new_pass)
                        if update_user_password(user_id, new_hash):
                            st.success("🎉 Password updated successfully!")
                        else:
                            st.error("⚠️ Failed to update password. System error.")
                    except Exception as e:
                        st.error(f"⚠️ Password update failed: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_form:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 📝 Edit Personal Profile Info")
        with st.form("profile_form"):
            new_full_name = st.text_input("Full Name:", value=user["full_name"])
            new_email = st.text_input("Email Address:", value=user["email"])
            
            profile_submit = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            
            if profile_submit:
                s_full_name = sanitize_input(new_full_name)
                s_email = sanitize_input(new_email)
                
                if not s_full_name or not s_email:
                    st.error("⚠️ Full Name and Email fields cannot be empty.")
                    return
                    
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_regex, s_email):
                    st.error("⚠️ Please enter a valid email address.")
                    return
                    
                try:
                    if update_user_profile(user_id, s_full_name, s_email):
                        # Update session user details too
                        st.session_state["user"]["full_name"] = s_full_name
                        st.session_state["user"]["email"] = s_email
                        st.success("🎉 Profile information updated successfully!")
                        st.rerun()
                    else:
                        st.error("⚠️ No changes were made or update failed.")
                except DuplicateUserError as e:
                    st.error(f"⚠️ Update failed: {e}")
                except Exception as e:
                    st.error(f"⚠️ Error occurred during profile update: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
