import streamlit as st
import datetime
from db.sqlite_db import get_analytics_data

def render_analytics(user_id: int):
    """
    Renders the local statistics and charts analytics page.
    """
    st.markdown("<h2>📈 Scan Analytics & Performance Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; margin-top:-10px;'>Analyze your card library metrics and local AI performance logs.</p>", unsafe_allow_html=True)
    
    analytics = get_analytics_data(user_id)
    total_scans = analytics["total_scans"]
    
    if total_scans == 0:
        st.info("💡 No analytics data available yet. Please upload and save business cards to populate the charts.")
        return
        
    # Group daily scans by week for weekly stats
    weekly_scans = {}
    for date_str, count in analytics["daily_scans"].items():
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            yr, wk, _ = dt.isocalendar()
            week_key = f"{yr}-W{wk:02d}"
            weekly_scans[week_key] = weekly_scans.get(week_key, 0) + count
        except Exception:
            pass

    # Sort daily and weekly chronologically
    sorted_daily = sorted(analytics["daily_scans"].items())
    sorted_weekly = sorted(weekly_scans.items())
    
    # 1. Performance KPI Cards
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric("Total Cards Scanned", f"{total_scans}")
    col_kpi2.metric("Avg OCR Time", f"{analytics['avg_ocr_time']}s")
    col_kpi3.metric("Avg AI Inference", f"{analytics['avg_inf_time']}s")
    col_kpi4.metric("Avg Total Time", f"{analytics['avg_tot_time']}s")
    
    st.markdown("---")
    
    # 2. Charts Section
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("##### 📅 Daily Scan Count (Past 30 Days)")
        if sorted_daily:
            daily_data = {
                "Date": [item[0] for item in sorted_daily],
                "Scans Count": [item[1] for item in sorted_daily]
            }
            st.bar_chart(daily_data, x="Date", y="Scans Count", color="#3b82f6")
        else:
            st.info("No daily scan history found.")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("##### 🏢 Top 10 Most Common Companies")
        companies = analytics["most_common_companies"]
        if companies:
            comp_data = {
                "Company": [c["company"] for c in companies],
                "Count": [c["count"] for c in companies]
            }
            st.bar_chart(comp_data, x="Company", y="Count", color="#10b981")
        else:
            st.info("No company data available.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_right:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("##### 🗓️ Weekly Scan Count")
        if sorted_weekly:
            weekly_data = {
                "Week": [item[0] for item in sorted_weekly],
                "Scans Count": [item[1] for item in sorted_weekly]
            }
            st.bar_chart(weekly_data, x="Week", y="Scans Count", color="#a855f7")
        else:
            st.info("No weekly scan history found.")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("##### ⚡ Local Time Log: OCR vs Inference vs Total")
        history = analytics["processing_history"]
        if history:
            # chronological order
            history_rev = history[::-1]
            time_data = {
                "Upload": list(range(1, len(history_rev) + 1)),
                "OCR Time (s)": [h.get("ocr_time", 0.0) for h in history_rev],
                "AI Inference (s)": [h.get("inference_time", 0.0) for h in history_rev],
                "Total Time (s)": [h.get("total_time", 0.0) for h in history_rev]
            }
            st.line_chart(time_data, x="Upload", y=["OCR Time (s)", "AI Inference (s)", "Total Time (s)"])
        else:
            st.info("No processing logs found.")
        st.markdown("</div>", unsafe_allow_html=True)
