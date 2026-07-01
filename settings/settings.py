import streamlit as st
import os
import shutil
import glob
from datetime import datetime
from utils.config import CACHE_DIR, LOG_DIR, DATABASE_PATH
from utils.logger import get_logger

logger = get_logger("settings")

def init_settings_state():
    """
    Initializes local configuration settings in Streamlit session state.
    """
    if "settings_theme" not in st.session_state:
        st.session_state["settings_theme"] = "dark"
    if "settings_export_folder" not in st.session_state:
        st.session_state["settings_export_folder"] = os.path.abspath("output")
    if "settings_ocr_cache" not in st.session_state:
        st.session_state["settings_ocr_cache"] = True
    if "settings_ai_cache" not in st.session_state:
        st.session_state["settings_ai_cache"] = True

def render_settings(user_id: int):
    """
    Renders the local settings page.
    """
    init_settings_state()
    
    st.markdown("<h2>⚙️ Application Settings</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; margin-top:-10px;'>Configure local caching, themes, folders, and SQLite backup procedures.</p>", unsafe_allow_html=True)
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 🎨 Preferences & Paths")
        
        # 1. Dark/Light Theme Toggle
        theme_options = ["dark", "light"]
        current_theme_idx = theme_options.index(st.session_state["settings_theme"])
        new_theme = st.selectbox(
            "Select Theme:",
            options=theme_options,
            index=current_theme_idx,
            format_func=lambda x: "✨ Dark Glassmorphism" if x == "dark" else "☀️ Classic Light"
        )
        if new_theme != st.session_state["settings_theme"]:
            st.session_state["settings_theme"] = new_theme
            logger.info(f"Theme switched to: {new_theme}")
            st.rerun()
            
        # 2. Default Export Folder
        export_folder = st.text_input(
            "Default Export Folder Path:",
            value=st.session_state["settings_export_folder"],
            help="Absolute path where exported contact JSONs will be saved by default."
        )
        if export_folder != st.session_state["settings_export_folder"]:
            # Validate directory
            try:
                os.makedirs(export_folder, exist_ok=True)
                st.session_state["settings_export_folder"] = os.path.abspath(export_folder)
                st.success("Export folder path updated!")
                logger.info(f"Updated default export folder to: {export_folder}")
            except Exception as e:
                st.error(f"Invalid path or permissions: {e}")
                
        # 3. Caching Toggles
        st.markdown("##### Caching Behaviors")
        st.session_state["settings_ocr_cache"] = st.checkbox(
            "Enable OCR Caching", 
            value=st.session_state["settings_ocr_cache"],
            help="Saves and reuses Tesseract results for identical image uploads."
        )
        st.session_state["settings_ai_cache"] = st.checkbox(
            "Enable Local AI Caching", 
            value=st.session_state["settings_ai_cache"],
            help="Saves and reuses TinyLlama extraction results for identical image uploads."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # 4. Maintenance / Cache Cleanup
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 🧹 System Maintenance")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🧹 Clear Local Cache", use_container_width=True):
                try:
                    cleared_count = 0
                    for file in glob.glob(os.path.join(CACHE_DIR, "*.json")):
                        os.remove(file)
                        cleared_count += 1
                    st.success(f"Cleared {cleared_count} cached file(s) successfully.")
                    logger.info("User cleared caching directory.")
                except Exception as e:
                    st.error(f"Failed to clear cache: {e}")
                    
        with col_btn2:
            if st.button("📝 Clear Local Logs", use_container_width=True):
                log_file = os.path.join(LOG_DIR, "app.log")
                if os.path.exists(log_file):
                    try:
                        # Open in write mode to truncate
                        with open(log_file, "w", encoding="utf-8") as f:
                            f.write("")
                        st.success("Logs cleared successfully.")
                        logger.info("User truncated log file.")
                    except Exception as e:
                        st.error(f"Failed to clear logs: {e}")
                else:
                    st.info("Log file is already empty.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("### 💾 Database Backup & Restore")
        
        # 1. Database Backup
        backup_dir = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        if st.button("💾 Create Database Backup", type="primary", use_container_width=True):
            if os.path.exists(DATABASE_PATH):
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"contacts_backup_{ts}.db"
                    backup_path = os.path.join(backup_dir, backup_name)
                    shutil.copy(DATABASE_PATH, backup_path)
                    st.success(f"Backup created: `{backup_name}`")
                    logger.info(f"Database backed up to: {backup_path}")
                except Exception as e:
                    st.error(f"Database backup failed: {e}")
            else:
                st.error("Active database not found to back up.")
                
        st.markdown("---")
        
        # 2. Database Restore
        st.markdown("##### Restore Database from Backup")
        # List existing backups
        backup_files = glob.glob(os.path.join(backup_dir, "contacts_backup_*.db"))
        backup_files = sorted(backup_files, reverse=True)
        
        if not backup_files:
            st.info("No local backups found in backups folder.")
        else:
            backup_names = [os.path.basename(f) for f in backup_files]
            selected_backup_name = st.selectbox("Select backup file to restore:", options=backup_names)
            
            # Warn before restoring
            st.warning("⚠️ Restoring a backup will overwrite the current database. All current changes will be lost.")
            
            if st.button("⏪ Restore Selected Backup", use_container_width=True):
                selected_backup_path = os.path.join(backup_dir, selected_backup_name)
                if os.path.exists(selected_backup_path):
                    try:
                        # Copy backup over current db
                        shutil.copy(selected_backup_path, DATABASE_PATH)
                        st.success("🎉 Database restored successfully! Reloading...")
                        logger.info(f"Database restored from: {selected_backup_path}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to restore database: {e}")
                else:
                    st.error("Selected backup file could not be found.")
        st.markdown("</div>", unsafe_allow_html=True)
