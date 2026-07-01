import pytesseract
import streamlit as st
import os
import hashlib
import json
import time
from datetime import datetime
from PIL import Image
import numpy as np
import cv2

# Project Imports
from utils.logger import setup_logger, get_logger
from utils.config import (
    MODEL_PATH, MODEL_URL, TESSERACT_CMD, DATABASE_PATH,
    UPLOADS_DIR, CACHE_DIR, LOG_DIR, LOG_LEVEL,
    get_tesseract_status, check_model_exists, download_model
)
from utils.performance import Timer, measure_time, get_process_resources, log_metrics
from utils.validators import validate_and_correct_json, BusinessCardInfo
from db.sqlite_db import (
    init_db, insert_contact, get_contact_by_hash, DuplicateContactError
)
from ocr.extractor import preprocess_image_pipeline, extract_text_and_confidence
from llm.parser import extract_structured_data

# Auth and Views Imports
from auth.session import (
    init_session, check_session_timeout, is_logged_in, logout_user, add_recent_search
)
from auth.security import sanitize_input
from auth.login import render_login
from auth.register import render_register
from dashboard.dashboard import render_dashboard
from dashboard.analytics import render_analytics
from user_profile.profile import render_profile
from settings.settings import render_settings, init_settings_state
from contacts.contacts_manager import render_contacts_manager

# Initialize logger and DB
setup_logger(LOG_DIR, LOG_LEVEL)
logger = get_logger("app")
init_db()

# Streamlit Page Config
st.set_page_config(
    page_title="Offline Business Card Scanner",
    page_icon="📇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session variables
init_session()
init_settings_state()
check_session_timeout()

# Theme CSS Injection based on settings
theme = st.session_state.get("settings_theme", "dark")
if theme == "light":
    theme_css = """
    /* Light Theme overrides */
    .stApp {
        background: #f8fafc !important;
        color: #0f172a !important;
    }
    
    .glass-card {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        color: #0f172a !important;
    }
    .glass-card:hover {
        border-color: rgba(20, 184, 166, 0.6) !important;
        transform: translateY(-2px);
    }
    
    .app-subtitle, p, span, label {
        color: #334155 !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
    }
    """
else:
    # Dark Theme
    theme_css = """
    /* Dark Theme */
    .stApp {
        background: radial-gradient(circle at top left, #1e293b, #0f172a) !important;
        color: #e2e8f0 !important;
    }
    
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        color: #e2e8f0 !important;
    }
    .glass-card:hover {
        border-color: rgba(20, 184, 166, 0.4) !important;
        transform: translateY(-2px);
    }
    
    .app-subtitle, p, span, label {
        color: #94a3b8 !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f8fafc !important;
    }
    """

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Outfit', sans-serif;
    }}
    
    {theme_css}
    
    /* Header styling */
    .app-header {{
        font-weight: 700;
        background: linear-gradient(135deg, #14b8a6, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        margin-top: -30px;
    }}
    
    /* Badge styling */
    .metric-badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-right: 8px;
    }}
    
    .badge-cache {{
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    
    .badge-live {{
        background-color: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }}
    
    .badge-fallback {{
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }}
</style>
""", unsafe_allow_html=True)

# Helper function to compute file SHA-256 hash
def get_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

# Helper function to check/load cache (respecting settings)
def get_cached_result(file_hash: str) -> tuple[bool, dict]:
    # Check if cache is globally enabled in settings
    ocr_enabled = st.session_state.get("settings_ocr_cache", True)
    ai_enabled = st.session_state.get("settings_ai_cache", True)
    
    if not ocr_enabled and not ai_enabled:
        return False, {}
        
    cache_path = os.path.join(CACHE_DIR, f"{file_hash}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # If only OCR is enabled, strip LLM outputs from cache to force live LLM run
                if ocr_enabled and not ai_enabled:
                    data["structured_json"] = {}
                    data["used_llm"] = False
                # If only AI is enabled (weird case, but let's handle), we can't do much without OCR text,
                # so if either is disabled we enforce matching behavior.
                return True, data
        except Exception as e:
            logger.error(f"Failed to read cache file {cache_path}: {e}")
    return False, {}

# Helper function to save cache
def save_cache_result(file_hash: str, data: dict):
    # Only write cache if enabled
    if not st.session_state.get("settings_ocr_cache", True) and not st.session_state.get("settings_ai_cache", True):
        return
        
    cache_path = os.path.join(CACHE_DIR, f"{file_hash}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved cache file: {cache_path}")
    except Exception as e:
        logger.error(f"Failed to write cache file {cache_path}: {e}")

# Render Header Title
st.markdown("<h1 class='app-header'>📇 Offline Business Card Scanner</h1>", unsafe_allow_html=True)

# ----------------- ROUTING FLOWS -----------------

if not is_logged_in():
    # RENDER UNAUTHENTICATED SCREEN (Login / Registration)
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    
    with col_l2:
        st.markdown("<div class='glass-card' style='margin-top: 30px;'>", unsafe_allow_html=True)
        
        # Segmented switch between login and register
        auth_mode = st.radio(
            "Account Authentication Options:",
            options=["Sign In", "Create Account"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        if auth_mode == "Sign In":
            render_login()
        else:
            render_register()
            
        st.markdown("</div>", unsafe_allow_html=True)
else:
    # RENDER AUTHENTICATED SCREEN (Sidebar Routing & Page Rendering)
    user_id = st.session_state["user"]["id"]
    
    # Available sidebar navigation pages
    pages = ["Dashboard", "Scan Business Card", "Saved Contacts", "Analytics", "Profile", "Settings", "Logout"]
    
    # Align selection index with state
    if st.session_state["current_page"] not in pages:
        st.session_state["current_page"] = "Dashboard"
    page_idx = pages.index(st.session_state["current_page"])
    
    # SIDEBAR CONFIG & NAVIGATION
    with st.sidebar:
        st.markdown(f"👤 **Logged in as:**\n`{st.session_state['user']['full_name']}`")
        st.markdown("---")
        
        selected_page = st.sidebar.radio(
            "Navigation Menu:",
            options=pages,
            index=page_idx,
            format_func=lambda x: {
                "Dashboard": "📊 Dashboard",
                "Scan Business Card": "📤 Scan Business Card",
                "Saved Contacts": "📋 Saved Contacts",
                "Analytics": "📈 Analytics",
                "Profile": "👤 User Profile",
                "Settings": "⚙️ Settings",
                "Logout": "🚪 Logout"
            }[x]
        )
        
        # If user changed sidebar page manually, trigger state update & rerun
        if selected_page != st.session_state["current_page"]:
            st.session_state["current_page"] = selected_page
            st.rerun()
            
        st.markdown("---")
        # System Settings & Tesseract Path configurations (accessible in sidebar)
        st.markdown("### ⚙️ System Settings")
        tesseract_ok = get_tesseract_status()
        st.markdown(f"**Tesseract OCR Status:** {'🟢 Available' if tesseract_ok else '🔴 Not Found'}")
        
        new_tess_cmd = st.text_input(
            "Tesseract Path:",
            value=TESSERACT_CMD,
            help="Path to tesseract.exe"
        )
        if new_tess_cmd != TESSERACT_CMD:
            if os.path.exists(new_tess_cmd):
                pytesseract.pytesseract.tesseract_cmd = new_tess_cmd
                st.success("Tesseract path updated!")
                logger.info(f"Tesseract path updated by user to: {new_tess_cmd}")
            else:
                st.warning("Path not found on disk!")
                
        # Model GGUF verification
        model_exists = check_model_exists()
        st.markdown(f"**Local AI Model Status:** {'🟢 Loaded' if model_exists else '🔴 Missing'}")
        
        if not model_exists:
            st.info("TinyLlama model GGUF is missing. You can download it below.")
            if st.button("📥 Download TinyLlama"):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                def download_progress(downloaded, total_size):
                    if total_size > 0:
                        fraction = downloaded / total_size
                        progress_bar.progress(fraction)
                        status_text.text(f"Downloading: {downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB ({fraction*100:.1f}%)")
                if download_model(download_progress):
                    st.success("Downloaded! Refreshing...")
                    st.rerun()
                else:
                    st.error("Download failed.")
        
        st.markdown("---")
        # Resource Monitoring
        st.markdown("### 🖥️ Resource Monitoring")
        res = get_process_resources()
        col_cpu, col_mem = st.columns(2)
        with col_cpu:
            st.metric("Process CPU", f"{res['process_cpu_percent']:.1f}%")
            st.metric("System CPU", f"{res['system_cpu_percent']:.1f}%")
        with col_mem:
            st.metric("Process RAM", f"{res['process_memory_mb']} MB")
            st.metric("System RAM", f"{res['system_memory_percent']}%")

    # PAGE ROUTER
    if st.session_state["current_page"] == "Dashboard":
        render_dashboard(user_id)
        
    elif st.session_state["current_page"] == "Scan Business Card":
        # RENDER IMAGE SCANNER PIPELINE
        st.markdown("<h2>📤 Upload & Extract Business Card</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color: #94a3b8; margin-top:-10px;'>Upload a business card image to run local OpenCV enhancers, OCR, and AI JSON extraction.</p>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Choose a business card image...",
            type=["jpg", "jpeg", "png"],
            help="Supported formats: JPG, JPEG, PNG."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            file_hash = get_file_hash(file_bytes)
            filename = uploaded_file.name
            
            uploaded_image_path = os.path.join(UPLOADS_DIR, f"{file_hash}_{filename}")
            if not os.path.exists(uploaded_image_path):
                with open(uploaded_image_path, "wb") as f:
                    f.write(file_bytes)
                    
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            col_img, col_proc = st.columns([1, 2])
            
            with col_img:
                st.markdown("#### Image Preview")
                st.image(uploaded_image_path, use_column_width=True, caption=filename)
                
            with col_proc:
                st.markdown("#### Extraction Processing Console")
                
                # Check cache (complying to settings)
                cached_exists, cache_data = get_cached_result(file_hash)
                
                total_timer = Timer().start()
                ocr_timer = Timer()
                llm_timer = Timer()
                
                ocr_text = ""
                ocr_confidence = 0.0
                structured_json = {}
                used_cache = False
                used_llm = True
                preprocessed_debug_path = os.path.join(UPLOADS_DIR, f"{file_hash}_preprocessed.png")
                
                # Retrieve from cache if enabled and present
                # Cache requires both OCR and AI Cache to be stored, otherwise we run live steps
                ocr_cache_enabled = st.session_state.get("settings_ocr_cache", True)
                ai_cache_enabled = st.session_state.get("settings_ai_cache", True)
                
                if cached_exists and (ocr_cache_enabled and (not used_llm or (used_llm and ai_cache_enabled))):
                    used_cache = True
                    ocr_text = cache_data.get("ocr_text", "")
                    ocr_confidence = cache_data.get("ocr_confidence", 0.0)
                    structured_json = cache_data.get("structured_json", {})
                    used_llm = cache_data.get("used_llm", True)
                    
                    ocr_time = cache_data.get("ocr_time", 0.0)
                    inference_time = cache_data.get("inference_time", 0.0)
                    total_time = cache_data.get("total_time", 0.0)
                    
                    total_timer.stop()
                    total_timer.elapsed = total_time
                    st.markdown("<span class='metric-badge badge-cache'>💾 Loaded from local cache</span>", unsafe_allow_html=True)
                    
                    if not os.path.exists(preprocessed_debug_path):
                        try:
                            _, pre_img, _ = preprocess_image_pipeline(uploaded_image_path, preprocessed_debug_path)
                        except Exception:
                            pass
                else:
                    # Live execution
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()
                    
                    try:
                        # Step 1: Preprocessing
                        status_text.text("Step 1: Enhancing image with OpenCV...")
                        progress_bar.progress(0.2)
                        
                        ocr_timer.start()
                        original_img, preprocessed_img, rot_angle = preprocess_image_pipeline(
                            uploaded_image_path, preprocessed_debug_path
                        )
                        
                        # Step 2: OCR text extraction
                        status_text.text("Step 2: Performing OCR using local Tesseract...")
                        progress_bar.progress(0.5)
                        ocr_text, ocr_confidence = extract_text_and_confidence(preprocessed_img)
                        ocr_timer.stop()
                        
                        # Step 3: LLM Parsing
                        status_text.text("Step 3: Extracting structure with local TinyLlama Chat model (CPU)...")
                        progress_bar.progress(0.8)
                        
                        llm_timer.start()
                        structured_json, used_llm = extract_structured_data(ocr_text)
                        llm_timer.stop()
                        
                        total_timer.stop()
                        
                        ocr_time = ocr_timer.elapsed
                        inference_time = llm_timer.elapsed
                        total_time = total_timer.elapsed
                        
                        status_text.empty()
                        progress_bar.empty()
                        
                        log_metrics("OCR", ocr_timer, get_process_resources())
                        log_metrics("LLM", llm_timer, get_process_resources())
                        
                        # Cache the result
                        save_cache_result(file_hash, {
                            "ocr_text": ocr_text,
                            "ocr_confidence": ocr_confidence,
                            "structured_json": structured_json,
                            "used_llm": used_llm,
                            "ocr_time": ocr_time,
                            "inference_time": inference_time,
                            "total_time": total_time
                        })
                        st.markdown("<span class='metric-badge badge-live'>⚡ Live AI Pipeline Executed</span>", unsafe_allow_html=True)
                        if not used_llm:
                            st.markdown("<span class='metric-badge badge-fallback'>⚠️ AI Failed - Regex Fallback Applied</span>", unsafe_allow_html=True)
                            
                    except Exception as e:
                        status_text.empty()
                        progress_bar.empty()
                        st.error(f"Failed to process image: {e}")
                        logger.error(f"Image pipeline failed: {e}", exc_info=True)
                        total_timer.stop()
                        ocr_time, inference_time, total_time = 0.0, 0.0, 0.0
                
                st.success("Extraction complete!")
                
                # Check DB presence (user-isolated)
                db_contact = get_contact_by_hash(user_id, file_hash)
                is_saved = db_contact is not None
                
                col_save_btn, _ = st.columns([1.5, 2])
                with col_save_btn:
                    if is_saved:
                        st.info("💾 Saved in Database.")
                    else:
                        if st.button("💾 Save Contact to Database", type="primary", use_container_width=True):
                            try:
                                insert_contact(
                                    user_id=user_id,
                                    image_hash=file_hash,
                                    image_filename=filename,
                                    upload_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    ocr_text=ocr_text,
                                    structured_json=structured_json,
                                    ocr_time=ocr_time,
                                    inference_time=inference_time,
                                    total_time=total_time
                                )
                                st.success("Successfully saved to database!")
                                st.rerun()
                            except DuplicateContactError as de:
                                st.warning("Contact already exists.")
                            except Exception as e:
                                st.error(f"Failed to save contact: {e}")
                                
                # Results Tabs
                res_tabs = st.tabs(["📇 Extracted Data", "📝 Raw OCR Text", "📷 Preprocessed Image", "📈 Metrics"])
                with res_tabs[0]:
                    col_fld, col_j = st.columns(2)
                    with col_fld:
                        st.markdown("##### Structured Fields")
                        st.text_input("Name:", value=structured_json.get("name", ""), disabled=True)
                        st.text_input("Designation / Title:", value=structured_json.get("designation", ""), disabled=True)
                        st.text_input("Company / Organization:", value=structured_json.get("company", ""), disabled=True)
                        st.text_input("Phone:", value=structured_json.get("phone", ""), disabled=True)
                        st.text_input("Email:", value=structured_json.get("email", ""), disabled=True)
                        st.text_input("Website:", value=structured_json.get("website", ""), disabled=True)
                        st.text_area("Address:", value=structured_json.get("address", ""), disabled=True, height=80)
                    with col_j:
                        st.markdown("##### JSON Output")
                        st.code(json.dumps(structured_json, indent=2), language="json")
                        
                with res_tabs[1]:
                    st.markdown(f"**Average Word Confidence Score:** `{ocr_confidence}%`")
                    st.text_area("Raw Text extracted by Tesseract:", value=ocr_text, height=300)
                with res_tabs[2]:
                    st.markdown("##### Binarized & Deskewed OpenCV Result")
                    if os.path.exists(preprocessed_debug_path):
                        st.image(preprocessed_debug_path, use_column_width=True)
                    else:
                        st.warning("Preprocessed debug image not saved.")
                with res_tabs[3]:
                    st.markdown("##### Performance Metrics")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("OCR Time", f"{ocr_time:.2f}s")
                    col_m2.metric("Inference Time", f"{inference_time:.2f}s")
                    col_m3.metric("Total Time", f"{total_time:.2f}s")
            st.markdown("</div>", unsafe_allow_html=True)
            
    elif st.session_state["current_page"] == "Saved Contacts":
        render_contacts_manager(user_id)
        
    elif st.session_state["current_page"] == "Analytics":
        render_analytics(user_id)
        
    elif st.session_state["current_page"] == "Profile":
        render_profile(user_id)
        
    elif st.session_state["current_page"] == "Settings":
        render_settings(user_id)
        
    elif st.session_state["current_page"] == "Logout":
        logout_user()
        st.success("Successfully logged out.")
        st.rerun()
