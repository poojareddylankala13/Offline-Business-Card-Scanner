import streamlit as st
import os
from db.sqlite_db import get_user_stats, get_all_contacts
from auth.session import init_session

def render_dashboard(user_id: int):
    """
    Renders the professional Dashboard for the authenticated user.
    """
    init_session()
    
    # 1. Fetch user stats and recent contacts
    stats = get_user_stats(user_id)
    all_contacts = get_all_contacts(user_id)
    recent_contacts = all_contacts[:5]
    
    st.markdown(f"<h2>👋 Welcome Back, {st.session_state['user']['full_name']}!</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; margin-top:-10px;'>Here is your local business card scanning activity overview.</p>", unsafe_allow_html=True)
    
    # 2. KPI Cards Grid
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    with col_kpi1:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; padding: 15px;">
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 5px;">📇 Total Cards</p>
            <h2 style="color: #14b8a6; font-size: 2.2rem; font-weight: 700; margin: 0;">{stats['total_cards']}</h2>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi2:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; padding: 15px;">
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 5px;">⚡ Scans Today</p>
            <h2 style="color: #3b82f6; font-size: 2.2rem; font-weight: 700; margin: 0;">{stats['cards_today']}</h2>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi3:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; padding: 15px;">
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 5px;">🏢 Total Companies</p>
            <h2 style="color: #a855f7; font-size: 2.2rem; font-weight: 700; margin: 0;">{stats['total_companies']}</h2>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi4:
        # Format last scan time
        lst = stats['last_scan_time']
        if lst != "Never":
            try:
                # Format to short date
                lst = lst.split(" ")[0]
            except Exception:
                pass
        st.markdown(f"""
        <div class="glass-card" style="text-align: center; padding: 15px;">
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 5px;">🕒 Last Scan</p>
            <h2 style="color: #f59e0b; font-size: 1.6rem; font-weight: 700; margin: 10px 0 0 0;">{lst}</h2>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    # 3. Main Split Section: Quick Actions & Recent Activity
    col_left, col_right = st.columns([1, 1.2])
    
    with col_left:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### ⚡ Quick Actions")
        
        # Grid of Quick Action buttons using Streamlit columns
        col_qa1, col_qa2 = st.columns(2)
        with col_qa1:
            if st.button("📤 Scan New Card", use_container_width=True, type="primary"):
                st.session_state["current_page"] = "Scan Business Card"
                st.rerun()
            if st.button("🔍 Search Contacts", use_container_width=True):
                st.session_state["current_page"] = "Saved Contacts"
                st.rerun()
            if st.button("👤 View Profile", use_container_width=True):
                st.session_state["current_page"] = "Profile"
                st.rerun()
                
        with col_qa2:
            if st.button("📋 Saved Contacts", use_container_width=True):
                st.session_state["current_page"] = "Saved Contacts"
                st.rerun()
            if st.button("📈 View Analytics", use_container_width=True):
                st.session_state["current_page"] = "Analytics"
                st.rerun()
            if st.button("⚙️ Local Settings", use_container_width=True):
                st.session_state["current_page"] = "Settings"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Recent Searches Card
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 🔍 Recent Searches")
        history = st.session_state.get("recent_searches", [])
        if not history:
            st.info("No recent search queries stored in this session.")
        else:
            st.write("Click on a past query to open it in Saved Contacts:")
            for q in history:
                # We render a button-like trigger
                if st.button(f"🔎 {q}", key=f"hist_{q}", use_container_width=True):
                    # Set search query filter in session state
                    st.session_state["search_filter_query"] = q
                    st.session_state["current_page"] = "Saved Contacts"
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_right:
        st.markdown("<div class='glass-card' style='height: 100%; min-height: 420px;'>", unsafe_allow_html=True)
        st.markdown("### 📝 Recent Activity")
        
        if not recent_contacts:
            st.info("You haven't scanned any business cards yet. Click 'Scan New Card' to start!")
        else:
            st.write("Latest business cards scanned by you:")
            for idx, contact in enumerate(recent_contacts):
                sj = contact["structured_json"]
                name = sj.get("name", "Unnamed")
                company = sj.get("company", "No Company")
                phone = sj.get("phone", "")
                email = sj.get("email", "")
                timestamp = contact.get("upload_timestamp", "")
                
                st.markdown(f"""
                <div style="border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 8px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #f8fafc; font-size: 1.05rem;">{name}</strong>
                        <span style="color: #64748b; font-size: 0.8rem;">{timestamp}</span>
                    </div>
                    <div style="color: #0284c7; font-size: 0.9rem; font-weight: 600;">{company}</div>
                    <div style="color: #94a3b8; font-size: 0.85rem; display: flex; gap: 15px;">
                        <span>📞 {phone}</span>
                        <span>✉️ {email}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            if st.button("View All Contacts", use_container_width=True):
                st.session_state["current_page"] = "Saved Contacts"
                st.rerun()
                
        st.markdown("</div>", unsafe_allow_html=True)
