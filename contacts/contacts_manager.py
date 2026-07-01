import streamlit as st
import json
import os
from db.sqlite_db import get_all_contacts, search_contacts, delete_contact, edit_contact
from utils.config import UPLOADS_DIR
from auth.session import add_recent_search

ITEMS_PER_PAGE = 8

def render_contacts_manager(user_id: int):
    """
    Renders the dedicated Contacts Manager view with pagination, search, filters,
    sorting, inline edit, delete, and export features.
    """
    st.markdown("<h2>📋 Saved Business Card Contacts</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; margin-top:-10px;'>Manage your scanned contact database, edit details, and export data offline.</p>", unsafe_allow_html=True)

    # 1. Search and Filters
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    col_s1, col_s2, col_s3, col_s4 = st.columns([1.5, 1, 1, 1])
    
    # Prefill query if accessed from recent searches
    default_search = st.session_state.get("search_filter_query", "")
    # Clear the session state so it doesn't lock it
    if "search_filter_query" in st.session_state:
        del st.session_state["search_filter_query"]
        
    with col_s1:
        search_query = st.text_input("🔍 Search Contacts:", value=default_search, placeholder="Search by name, company, email, phone...")
        if search_query:
            add_recent_search(search_query)
            
    with col_s2:
        # Sorting
        sort_by = st.selectbox(
            "Sort By:",
            options=["Newest", "Oldest", "Alphabetical (A-Z)", "Alphabetical (Z-A)"]
        )
        
    # Get initial search results
    contacts = search_contacts(user_id, search_query)
    
    # Companies filter options
    all_companies = sorted(list(set(c["structured_json"].get("company", "").strip() for c in contacts if c["structured_json"].get("company"))))
    
    with col_s3:
        company_filter = st.selectbox(
            "Filter by Company:",
            options=["All"] + all_companies
        )
        
    # Designations filter options
    all_titles = sorted(list(set(c["structured_json"].get("designation", "").strip() for c in contacts if c["structured_json"].get("designation"))))
    
    with col_s4:
        title_filter = st.selectbox(
            "Filter by Title:",
            options=["All"] + all_titles
        )
        
    st.markdown("</div>", unsafe_allow_html=True)

    # 2. Filter contacts Python-side
    filtered_contacts = []
    for c in contacts:
        sj = c["structured_json"]
        comp = sj.get("company", "").strip()
        title = sj.get("designation", "").strip()
        
        # Apply company filter
        if company_filter != "All" and comp != company_filter:
            continue
        # Apply designation filter
        if title_filter != "All" and title != title_filter:
            continue
            
        filtered_contacts.append(c)
        
    # 3. Sort contacts
    if sort_by == "Newest":
        # Already ordered by created_at DESC from database
        pass
    elif sort_by == "Oldest":
        filtered_contacts.reverse()
    elif sort_by == "Alphabetical (A-Z)":
        filtered_contacts.sort(key=lambda x: x["structured_json"].get("name", "").lower())
    elif sort_by == "Alphabetical (Z-A)":
        filtered_contacts.sort(key=lambda x: x["structured_json"].get("name", "").lower(), reverse=True)

    # If edit or view mode is active, display the dialog/overlay
    # We use Streamlit session state keys to track if we are currently editing or viewing a specific contact ID
    if "edit_contact_id" in st.session_state:
        render_edit_modal(user_id, st.session_state["edit_contact_id"])
        return
        
    if "view_contact_id" in st.session_state:
        render_view_modal(user_id, st.session_state["view_contact_id"])
        return

    if not filtered_contacts:
        st.info("💡 No contacts match your search or filter options.")
        return

    # 4. View Mode Toggle (Table vs. Cards)
    col_view, col_page = st.columns([2, 1])
    with col_view:
        view_mode = st.radio("View Mode:", ["🃏 Card Grid", "📋 Table View"], horizontal=True)
        
    # 5. Pagination
    total_items = len(filtered_contacts)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Store current page in state
    if "contacts_page" not in st.session_state:
        st.session_state["contacts_page"] = 1
        
    # Handle bounds
    if st.session_state["contacts_page"] > total_pages:
        st.session_state["contacts_page"] = max(1, total_pages)
        
    with col_page:
        if total_pages > 1:
            page_numbers = list(range(1, total_pages + 1))
            st.session_state["contacts_page"] = st.selectbox(
                "Page:",
                options=page_numbers,
                index=st.session_state["contacts_page"] - 1
            )
            
    # Slice items for current page
    start_idx = (st.session_state["contacts_page"] - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
    page_contacts = filtered_contacts[start_idx:end_idx]
    
    st.markdown(f"<p style='color: #64748b; font-size: 0.9rem;'>Showing {start_idx + 1}-{end_idx} of {total_items} contacts</p>", unsafe_allow_html=True)
    
    # 6. Render Data
    if view_mode == "📋 Table View":
        render_table_layout(user_id, page_contacts)
    else:
        render_cards_layout(user_id, page_contacts)

def render_table_layout(user_id: int, contacts: list):
    """
    Renders page contacts in a compact tabular column layout with inline action triggers.
    """
    # Header row
    st.markdown("""
    <div style="display: flex; border-bottom: 2px solid rgba(255,255,255,0.1); padding-bottom: 8px; font-weight: bold; color: #94a3b8; font-size: 0.95rem;">
        <div style="flex: 1.5;">👤 Name</div>
        <div style="flex: 1.5;">🏢 Company</div>
        <div style="flex: 1.5;">👔 Title</div>
        <div style="flex: 1.5;">✉️ Email</div>
        <div style="flex: 1.2;">⚙️ Actions</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)
    
    for c in contacts:
        sj = c["structured_json"]
        c_id = c["id"]
        
        name = sj.get("name", "Unnamed")
        company = sj.get("company", "")
        title = sj.get("designation", "")
        email = sj.get("email", "")
        
        # Render a single row
        col_name, col_comp, col_title, col_email, col_act = st.columns([1.5, 1.5, 1.5, 1.5, 1.2])
        
        with col_name:
            st.markdown(f"<div style='padding-top: 5px; font-weight: 600; color: #f8fafc;'>{name}</div>", unsafe_allow_html=True)
        with col_comp:
            st.markdown(f"<div style='padding-top: 5px; color: #0284c7;'>{company}</div>", unsafe_allow_html=True)
        with col_title:
            st.markdown(f"<div style='padding-top: 5px; color: #cbd5e1;'>{title}</div>", unsafe_allow_html=True)
        with col_email:
            st.markdown(f"<div style='padding-top: 5px; color: #94a3b8; font-size: 0.85rem;'>{email}</div>", unsafe_allow_html=True)
            
        with col_act:
            # Inline button triggers
            col_v, col_e, col_d = st.columns(3)
            with col_v:
                if st.button("👁️", key=f"tbl_v_{c_id}", help="View Details"):
                    st.session_state["view_contact_id"] = c_id
                    st.rerun()
            with col_e:
                if st.button("📝", key=f"tbl_e_{c_id}", help="Edit Contact"):
                    st.session_state["edit_contact_id"] = c_id
                    st.rerun()
            with col_d:
                if st.button("🗑️", key=f"tbl_d_{c_id}", help="Delete Contact"):
                    if delete_contact(user_id, c_id):
                        st.success("Deleted successfully!")
                        st.rerun()
                        
        st.markdown("<div style='border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 5px; padding-bottom: 5px;'></div>", unsafe_allow_html=True)

def render_cards_layout(user_id: int, contacts: list):
    """
    Renders contacts in a responsive grid of card layouts.
    """
    # 2 columns of cards
    col_c1, col_c2 = st.columns(2)
    
    for idx, c in enumerate(contacts):
        target_col = col_c1 if idx % 2 == 0 else col_c2
        sj = c["structured_json"]
        c_id = c["id"]
        
        name = sj.get("name", "Unnamed")
        company = sj.get("company", "No Company Specified")
        title = sj.get("designation", "")
        phone = sj.get("phone", "")
        email = sj.get("email", "")
        
        with target_col:
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom: 15px; padding: 18px;">
                <div style="font-weight: 700; color: #f8fafc; font-size: 1.15rem; margin-bottom: 3px;">👤 {name}</div>
                <div style="color: #64748b; font-size: 0.9rem; font-weight: 600; text-transform: uppercase; margin-bottom: 5px;">{title}</div>
                <div style="color: #14b8a6; font-weight: 600; margin-bottom: 10px;">🏢 {company}</div>
                <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 12px; line-height: 1.4;">
                    <span>📞 {phone}</span><br>
                    <span>✉️ {email}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action triggers inside cards (re-renders below the html text)
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1:
                if st.button("👁️ View", key=f"crd_v_{c_id}", use_container_width=True):
                    st.session_state["view_contact_id"] = c_id
                    st.rerun()
            with col_b2:
                if st.button("📝 Edit", key=f"crd_e_{c_id}", use_container_width=True):
                    st.session_state["edit_contact_id"] = c_id
                    st.rerun()
            with col_b3:
                if st.button("🗑️ Delete", key=f"crd_d_{c_id}", use_container_width=True):
                    if delete_contact(user_id, c_id):
                        st.success("Deleted successfully!")
                        st.rerun()
            with col_b4:
                # Direct export
                if st.button("📥 Export", key=f"crd_x_{c_id}", use_container_width=True):
                    export_contact_json(c)
                    
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

def export_contact_json(contact: dict):
    """
    Exports a single contact JSON block into the configured export folder.
    """
    export_dir = st.session_state.get("settings_export_folder", os.path.abspath("output"))
    os.makedirs(export_dir, exist_ok=True)
    
    sj = contact["structured_json"]
    safe_name = sj.get("name", "contact").replace(" ", "_").lower()
    filename = f"contact_{safe_name}_{contact['id']}.json"
    dest_path = os.path.join(export_dir, filename)
    
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(sj, f, indent=2, ensure_ascii=False)
        st.toast(f"Saved: {filename} to exports folder.")
    except Exception as e:
        st.error(f"Export failed: {e}")

def render_view_modal(user_id: int, contact_id: int):
    """
    Renders details, raw OCR text, image preview, and JSON copy utilities for a contact.
    """
    contacts = get_all_contacts(user_id)
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    
    if not contact:
        st.error("Contact details not found.")
        if st.button("↩️ Back to List"):
            del st.session_state["view_contact_id"]
            st.rerun()
        return
        
    sj = contact["structured_json"]
    
    col_back, col_actions = st.columns([3, 1])
    with col_back:
        if st.button("↩️ Back to Contacts List", type="secondary"):
            del st.session_state["view_contact_id"]
            st.rerun()
            
    with col_actions:
        st.download_button(
            label="📥 Export JSON",
            data=json.dumps(sj, indent=2),
            file_name=f"contact_{sj.get('name', 'contact').replace(' ', '_').lower()}.json",
            mime="application/json",
            use_container_width=True
        )

    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown(f"### 📇 Details for: {sj.get('name', 'Unnamed')}")
    
    col_det, col_img = st.columns([1.5, 1])
    
    with col_det:
        st.text_input("Name:", value=sj.get("name", ""), disabled=True)
        st.text_input("Designation / Job Title:", value=sj.get("designation", ""), disabled=True)
        st.text_input("Company / Organization:", value=sj.get("company", ""), disabled=True)
        st.text_input("Phone:", value=sj.get("phone", ""), disabled=True)
        st.text_input("Email:", value=sj.get("email", ""), disabled=True)
        st.text_input("Website:", value=sj.get("website", ""), disabled=True)
        st.text_area("Address:", value=sj.get("address", ""), disabled=True, height=80)
        
    with col_img:
        # Original uploaded image
        img_hash = contact["image_hash"]
        img_fname = contact["image_filename"]
        img_path = os.path.join(UPLOADS_DIR, f"{img_hash}_{img_fname}")
        if os.path.exists(img_path):
            st.image(img_path, caption="Original Card Image", use_column_width=True)
        else:
            st.warning("Original image file could not be found.")
            
    st.markdown("---")
    
    # Raw OCR text & JSON
    col_ocr, col_json = st.columns(2)
    with col_ocr:
        st.markdown("##### Raw Text Extracted by OCR:")
        st.text_area("", value=contact.get("ocr_text", ""), height=250, disabled=True)
    with col_json:
        st.markdown("##### Structured JSON Data:")
        st.code(json.dumps(sj, indent=2), language="json")
        
    st.markdown("</div>", unsafe_allow_html=True)

def render_edit_modal(user_id: int, contact_id: int):
    """
    Renders an inline form allowing the user to update details of a saved contact.
    """
    contacts = get_all_contacts(user_id)
    contact = next((c for c in contacts if c["id"] == contact_id), None)
    
    if not contact:
        st.error("Contact not found.")
        if st.button("↩️ Back to List"):
            del st.session_state["edit_contact_id"]
            st.rerun()
        return
        
    sj = contact["structured_json"]
    
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown(f"### 📝 Edit Details for: {sj.get('name', 'Unnamed')}")
    
    with st.form("edit_contact_form"):
        new_name = st.text_input("Name:", value=sj.get("name", ""))
        new_title = st.text_input("Designation / Title:", value=sj.get("designation", ""))
        new_company = st.text_input("Company / Organization:", value=sj.get("company", ""))
        new_phone = st.text_input("Phone Number:", value=sj.get("phone", ""))
        new_email = st.text_input("Email:", value=sj.get("email", ""))
        new_website = st.text_input("Website:", value=sj.get("website", ""))
        new_address = st.text_area("Address:", value=sj.get("address", ""), height=85)
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            submit_edit = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
        with col_btn2:
            cancel_edit = st.form_submit_button("Cancel", use_container_width=True)
            
        if cancel_edit:
            del st.session_state["edit_contact_id"]
            st.rerun()
            
        if submit_edit:
            updated_json = {
                "name": new_name.strip(),
                "designation": new_title.strip(),
                "company": new_company.strip(),
                "phone": new_phone.strip(),
                "email": new_email.strip().lower(),
                "website": new_website.strip(),
                "address": new_address.strip()
            }
            
            if edit_contact(user_id, contact_id, updated_json):
                st.success("🎉 Contact updated successfully!")
                del st.session_state["edit_contact_id"]
                st.rerun()
            else:
                st.error("⚠️ Failed to update contact details. Database error.")
                
    st.markdown("</div>", unsafe_allow_html=True)
