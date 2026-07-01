import sqlite3
import json
import os
import datetime
from typing import Dict, Any, List, Optional, Tuple
from utils.config import DATABASE_PATH
from utils.logger import get_logger

logger = get_logger("sqlite_db")

class DuplicateContactError(Exception):
    """Raised when trying to save a contact that already exists based on image hash and user."""
    pass

class DuplicateUserError(Exception):
    """Raised when registering a username or email that already exists."""
    pass

def get_connection() -> sqlite3.Connection:
    """
    Returns a connection to the SQLite database.
    """
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the SQLite database. Creates the users and contacts tables,
    and runs migrations if needed.
    """
    logger.info("Initializing SQLite database.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Check if contacts table exists, and get columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'")
        contacts_exists = cursor.fetchone() is not None
        
        if contacts_exists:
            cursor.execute("PRAGMA table_info(contacts)")
            columns = [row["name"] for row in cursor.fetchall()]
            
            if "user_id" not in columns:
                logger.info("Migrating contacts table: adding user_id column and composite index.")
                # Run migration using temporary table rename
                cursor.execute("ALTER TABLE contacts RENAME TO contacts_old")
                
                cursor.execute("""
                    CREATE TABLE contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        image_hash TEXT NOT NULL,
                        image_filename TEXT NOT NULL,
                        upload_timestamp TEXT NOT NULL,
                        ocr_text TEXT NOT NULL,
                        structured_json TEXT NOT NULL,
                        ocr_time REAL,
                        inference_time REAL,
                        total_time REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        UNIQUE(user_id, image_hash)
                    )
                """)
                
                # Copy data from contacts_old to contacts
                try:
                    cursor.execute("""
                        INSERT INTO contacts (
                            id, user_id, image_hash, image_filename, upload_timestamp, 
                            ocr_text, structured_json, ocr_time, inference_time, total_time, created_at
                        )
                        SELECT 
                            id, NULL, image_hash, image_filename, upload_timestamp, 
                            ocr_text, structured_json, ocr_time, inference_time, total_time, created_at
                        FROM contacts_old
                    """)
                    cursor.execute("DROP TABLE contacts_old")
                    logger.info("Contacts table migration completed successfully.")
                except sqlite3.Error as e:
                    logger.error(f"Migration failed during data copy: {e}. Restoring old table.")
                    cursor.execute("DROP TABLE IF EXISTS contacts")
                    cursor.execute("ALTER TABLE contacts_old RENAME TO contacts")
                    raise e
        else:
            # Table doesn't exist, create it fresh
            cursor.execute("""
                CREATE TABLE contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    image_hash TEXT NOT NULL,
                    image_filename TEXT NOT NULL,
                    upload_timestamp TEXT NOT NULL,
                    ocr_text TEXT NOT NULL,
                    structured_json TEXT NOT NULL,
                    ocr_time REAL,
                    inference_time REAL,
                    total_time REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, image_hash)
                )
            """)
            
        conn.commit()
        logger.info(f"Database schema setup ready at: {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise e
    finally:
        conn.close()

# --- USER MANAGEMENT CRUD ---

def create_user(full_name: str, username: str, email: str, password_hash: str) -> int:
    """
    Inserts a new user record.
    Raises DuplicateUserError if username or email already exists.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (full_name, username, email, password_hash)
            VALUES (?, ?, ?, ?)
        """, (full_name, username.strip(), email.strip().lower(), password_hash))
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"Created user: {username} (ID: {new_id})")
        return new_id
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "username" in msg:
            raise DuplicateUserError("Username is already taken.")
        elif "email" in msg:
            raise DuplicateUserError("Email address is already registered.")
        else:
            raise DuplicateUserError("Username or email already exists.")
    except sqlite3.Error as e:
        logger.error(f"Failed to create user: {e}")
        raise e
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves user by ID.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching user by ID: {e}")
        return None
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves user by username.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching user by username: {e}")
        return None
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves user by email.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching user by email: {e}")
        return None
    finally:
        conn.close()

def update_user_profile(user_id: int, full_name: str, email: str) -> bool:
    """
    Updates user personal details.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET full_name = ?, email = ?
            WHERE id = ?
        """, (full_name.strip(), email.strip().lower(), user_id))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated user profile for ID: {user_id}")
        return success
    except sqlite3.IntegrityError:
        raise DuplicateUserError("Email address is already in use by another account.")
    except sqlite3.Error as e:
        logger.error(f"Error updating user profile: {e}")
        return False
    finally:
        conn.close()

def update_user_password(user_id: int, password_hash: str) -> bool:
    """
    Updates user password hash.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (password_hash, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated user password for ID: {user_id}")
        return success
    except sqlite3.Error as e:
        logger.error(f"Error updating password: {e}")
        return False
    finally:
        conn.close()

# --- CONTACT MANAGEMENT CRUD (USER SPECIFIC) ---

def insert_contact(
    user_id: int,
    image_hash: str,
    image_filename: str,
    upload_timestamp: str,
    ocr_text: str,
    structured_json: Dict[str, str],
    ocr_time: float,
    inference_time: float,
    total_time: float
) -> int:
    """
    Inserts a new business card record associated with a user_id.
    Prevents duplicates per-user using the user_id + image_hash combination.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if hash already exists for this user
        cursor.execute("SELECT id FROM contacts WHERE user_id = ? AND image_hash = ?", (user_id, image_hash))
        existing = cursor.fetchone()
        if existing:
            msg = f"This business card has already been scanned by you."
            logger.warning(msg)
            raise DuplicateContactError(msg)

        json_str = json.dumps(structured_json)
        
        cursor.execute("""
            INSERT INTO contacts (
                user_id, image_hash, image_filename, upload_timestamp, ocr_text, 
                structured_json, ocr_time, inference_time, total_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, image_hash, image_filename, upload_timestamp, ocr_text,
            json_str, ocr_time, inference_time, total_time
        ))
        
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"Inserted contact ID: {new_id} for user ID: {user_id} ({image_filename})")
        return new_id
    except sqlite3.IntegrityError as e:
        msg = f"Database integrity violation, duplicate entry: {e}"
        logger.warning(msg)
        raise DuplicateContactError(msg)
    except sqlite3.Error as e:
        logger.error(f"Failed to insert contact: {e}")
        raise e
    finally:
        conn.close()

def edit_contact(user_id: int, contact_id: int, structured_json: Dict[str, str]) -> bool:
    """
    Updates the parsed JSON details of an existing contact.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        json_str = json.dumps(structured_json)
        cursor.execute("""
            UPDATE contacts
            SET structured_json = ?
            WHERE id = ? AND user_id = ?
        """, (json_str, contact_id, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated contact ID: {contact_id} details.")
        return success
    except sqlite3.Error as e:
        logger.error(f"Error editing contact: {e}")
        return False
    finally:
        conn.close()

def get_contact_by_hash(user_id: int, image_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a user's contact by its image hash.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contacts WHERE user_id = ? AND image_hash = ?", (user_id, image_hash))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["structured_json"] = json.loads(data["structured_json"])
            return data
        return None
    except sqlite3.Error as e:
        logger.error(f"Error checking contact hash: {e}")
        return None
    finally:
        conn.close()

def get_all_contacts(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves all contacts saved by a specific user, ordered by creation time descending.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contacts WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        
        contacts = []
        for row in rows:
            data = dict(row)
            data["structured_json"] = json.loads(data["structured_json"])
            contacts.append(data)
        return contacts
    except sqlite3.Error as e:
        logger.error(f"Error fetching contacts: {e}")
        return []
    finally:
        conn.close()

def search_contacts(user_id: int, search_query: str) -> List[Dict[str, Any]]:
    """
    Searches user contacts by Name, Company, Phone, or Email.
    """
    if not search_query.strip():
        return get_all_contacts(user_id)
        
    conn = get_connection()
    try:
        cursor = conn.cursor()
        q = f"%{search_query.strip()}%"
        
        cursor.execute("""
            SELECT * FROM contacts 
            WHERE user_id = ? AND (
               json_extract(structured_json, '$.name') LIKE ?
               OR json_extract(structured_json, '$.company') LIKE ?
               OR json_extract(structured_json, '$.phone') LIKE ?
               OR json_extract(structured_json, '$.email') LIKE ?
            )
            ORDER BY created_at DESC
        """, (user_id, q, q, q, q))
        
        rows = cursor.fetchall()
        contacts = []
        for row in rows:
            data = dict(row)
            data["structured_json"] = json.loads(data["structured_json"])
            contacts.append(data)
        return contacts
    except sqlite3.Error as e:
        logger.error(f"Error searching contacts: {e}")
        logger.info("Attempting python-side search fallback.")
        return python_fallback_search(user_id, search_query)
    finally:
        conn.close()

def python_fallback_search(user_id: int, search_query: str) -> List[Dict[str, Any]]:
    """
    Python-based search fallback in case sqlite json_extract throws an error.
    """
    all_contacts = get_all_contacts(user_id)
    q = search_query.strip().lower()
    if not q:
        return all_contacts
        
    filtered = []
    for c in all_contacts:
        sj = c.get("structured_json", {})
        name = sj.get("name", "").lower()
        company = sj.get("company", "").lower()
        phone = sj.get("phone", "").lower()
        email = sj.get("email", "").lower()
        
        if q in name or q in company or q in phone or q in email:
            filtered.append(c)
    return filtered

def delete_contact(user_id: int, contact_id: int) -> bool:
    """
    Deletes a contact by its ID, restricted to the logged-in user.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = ? AND user_id = ?", (contact_id, user_id))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Deleted contact ID: {contact_id} for user: {user_id}")
        else:
            logger.warning(f"Contact ID {contact_id} for user {user_id} not found to delete.")
        return success
    except sqlite3.Error as e:
        logger.error(f"Error deleting contact: {e}")
        return False
    finally:
        conn.close()

# --- ANALYTICS & STATS QUERIES ---

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """
    Gathers KPI statistics for the user dashboard.
    """
    conn = get_connection()
    stats = {
        "total_cards": 0,
        "cards_today": 0,
        "total_companies": 0,
        "last_scan_time": "Never"
    }
    try:
        cursor = conn.cursor()
        # 1. Total business cards
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE user_id = ?", (user_id,))
        stats["total_cards"] = cursor.fetchone()[0]
        
        # 2. Scans today
        today = datetime.datetime.now().strftime("%Y-%m-%d") + "%"
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE user_id = ? AND upload_timestamp LIKE ?", (user_id, today))
        stats["cards_today"] = cursor.fetchone()[0]
        
        # 3. Unique companies
        cursor.execute("""
            SELECT COUNT(DISTINCT NULLIF(json_extract(structured_json, '$.company'), ''))
            FROM contacts WHERE user_id = ?
        """, (user_id,))
        stats["total_companies"] = cursor.fetchone()[0]
        
        # 4. Last scan time
        cursor.execute("SELECT MAX(upload_timestamp) FROM contacts WHERE user_id = ?", (user_id,))
        last_time = cursor.fetchone()[0]
        if last_time:
            stats["last_scan_time"] = last_time
            
    except sqlite3.Error as e:
        logger.error(f"Error getting user stats: {e}")
    finally:
        conn.close()
    return stats

def get_analytics_data(user_id: int) -> Dict[str, Any]:
    """
    Gathers aggregation data for plotting analytics graphs.
    """
    conn = get_connection()
    data = {
        "total_scans": 0,
        "daily_scans": {},
        "weekly_scans": {},
        "most_common_companies": [],
        "avg_ocr_time": 0.0,
        "avg_inf_time": 0.0,
        "avg_tot_time": 0.0,
        "processing_history": []
    }
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE user_id = ?", (user_id,))
        data["total_scans"] = cursor.fetchone()[0]
        
        if data["total_scans"] > 0:
            # Average timing metrics
            cursor.execute("""
                SELECT AVG(ocr_time), AVG(inference_time), AVG(total_time)
                FROM contacts WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            data["avg_ocr_time"] = round(row[0] or 0.0, 2)
            data["avg_inf_time"] = round(row[1] or 0.0, 2)
            data["avg_tot_time"] = round(row[2] or 0.0, 2)
            
            # Most common companies
            cursor.execute("""
                SELECT json_extract(structured_json, '$.company') as comp, COUNT(*) as count
                FROM contacts WHERE user_id = ? AND comp != ''
                GROUP BY comp ORDER BY count DESC LIMIT 10
            """, (user_id,))
            data["most_common_companies"] = [{"company": r[0], "count": r[1]} for r in cursor.fetchall()]
            
            # Daily scans (latest 30 days)
            cursor.execute("""
                SELECT substr(upload_timestamp, 1, 10) as date_str, COUNT(*)
                FROM contacts WHERE user_id = ?
                GROUP BY date_str ORDER BY date_str DESC LIMIT 30
            """, (user_id,))
            data["daily_scans"] = {r[0]: r[1] for r in cursor.fetchall()}
            
            # Processing history (latest 50)
            cursor.execute("""
                SELECT id, image_filename, ocr_time, inference_time, total_time, upload_timestamp
                FROM contacts WHERE user_id = ?
                ORDER BY upload_timestamp DESC LIMIT 50
            """, (user_id,))
            data["processing_history"] = [dict(r) for r in cursor.fetchall()]
            
    except sqlite3.Error as e:
        logger.error(f"Error getting analytics data: {e}")
    finally:
        conn.close()
    return data
