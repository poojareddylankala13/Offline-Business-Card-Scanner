import unittest
import os
import json
import sqlite3
import shutil
from pathlib import Path

# Project imports
from utils.validators import validate_and_correct_json, extract_json_block, sanitize_json_string
from utils.performance import Timer, measure_time
from db.sqlite_db import (
    init_db, insert_contact, get_all_contacts, search_contacts, delete_contact,
    get_contact_by_hash, DuplicateContactError, get_connection,
    create_user, get_user_by_id, get_user_by_username, DuplicateUserError, edit_contact
)
from auth.security import hash_password, verify_password
from llm.parser import regex_fallback_extractor
from ocr.extractor import clean_ocr_text

class TestValidators(unittest.TestCase):
    
    def test_extract_json_block_markdown(self):
        text = "Here is the result:\n```json\n{\n  \"name\": \"John Doe\"\n}\n```\nHope it helps!"
        extracted = extract_json_block(text)
        self.assertEqual(extracted, '{\n  "name": "John Doe"\n}')

    def test_extract_json_block_braces(self):
        text = "Random text leading { \"key\": \"value\" } trailing text"
        extracted = extract_json_block(text)
        self.assertEqual(extracted, '{ "key": "value" }')

    def test_sanitize_json_trailing_comma(self):
        bad_json = '{\n  "name": "John Doe",\n  "designation": "Manager",\n}'
        sanitized = sanitize_json_string(bad_json)
        self.assertNotIn(',\n}', sanitized)
        
    def test_validate_and_correct_json_valid(self):
        raw = '{"name": "John Doe", "designation": "Architect", "company": "Cloud", "phone": "123", "email": "j@c.com", "website": "c.com", "address": "Boston"}'
        success, data, err = validate_and_correct_json(raw)
        self.assertTrue(success)
        self.assertEqual(data["name"], "John Doe")
        self.assertEqual(data["website"], "c.com")

    def test_validate_and_correct_json_missing_fields(self):
        raw = '{"name": "John Doe", "company": "Cloud", "phone": "123", "email": "j@c.com", "website": "c.com"}'
        success, data, err = validate_and_correct_json(raw)
        self.assertTrue(success)
        self.assertEqual(data["name"], "John Doe")
        self.assertEqual(data["address"], "")
        self.assertEqual(data["designation"], "")

    def test_validate_and_correct_json_malformed(self):
        raw = "This is not a JSON string at all."
        success, data, err = validate_and_correct_json(raw)
        self.assertFalse(success)
        self.assertEqual(data, {})

class TestSecurity(unittest.TestCase):
    
    def test_password_hashing_and_verification(self):
        pwd = "SecretPassword123"
        h = hash_password(pwd)
        self.assertNotEqual(pwd, h)
        self.assertTrue(verify_password(pwd, h))
        self.assertFalse(verify_password("wrong_password", h))

class TestDatabaseAndAuth(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        import utils.config
        cls.orig_db_path = utils.config.DATABASE_PATH
        utils.config.DATABASE_PATH = "database/test_contacts.db"
        
        os.makedirs(os.path.dirname(utils.config.DATABASE_PATH), exist_ok=True)
        if os.path.exists(utils.config.DATABASE_PATH):
            os.remove(utils.config.DATABASE_PATH)
            
        init_db()

    @classmethod
    def tearDownClass(cls):
        import utils.config
        if os.path.exists(utils.config.DATABASE_PATH):
            os.remove(utils.config.DATABASE_PATH)
        utils.config.DATABASE_PATH = cls.orig_db_path

    def setUp(self):
        # Clear tables
        conn = get_connection()
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM users")
        conn.commit()
        conn.close()
        
        # Create dummy users for testing
        self.u1_id = create_user("User One", "user1", "user1@test.com", hash_password("pass123"))
        self.u2_id = create_user("User Two", "user2", "user2@test.com", hash_password("pass456"))

    def test_create_user_and_duplicates(self):
        # Retrieve user by username
        u = get_user_by_username("user1")
        self.assertIsNotNone(u)
        self.assertEqual(u["full_name"], "User One")
        self.assertEqual(u["email"], "user1@test.com")
        
        # Test Duplicate Username
        with self.assertRaises(DuplicateUserError):
            create_user("User Three", "user1", "user3@test.com", "hash")
            
        # Test Duplicate Email
        with self.assertRaises(DuplicateUserError):
            create_user("User Four", "user4", "user1@test.com", "hash")

    def test_insert_and_retrieve_contact(self):
        h = "hash_test_123"
        cid = insert_contact(
            user_id=self.u1_id,
            image_hash=h,
            image_filename="test.png",
            upload_timestamp="2026-07-01 09:00:00",
            ocr_text="John Doe CloudScale Solutions",
            structured_json={"name": "John Doe", "designation": "Manager", "company": "CloudScale", "phone": "123", "email": "j@c.com", "website": "c.com", "address": "Boston"},
            ocr_time=0.5,
            inference_time=1.2,
            total_time=1.7
        )
        self.assertIsNotNone(cid)
        
        # Verify retrieved contact by hash
        contact = get_contact_by_hash(self.u1_id, h)
        self.assertIsNotNone(contact)
        self.assertEqual(contact["image_filename"], "test.png")
        self.assertEqual(contact["structured_json"]["name"], "John Doe")

    def test_user_data_isolation(self):
        h = "shared_card_hash"
        
        # User 1 inserts card
        insert_contact(
            user_id=self.u1_id,
            image_hash=h,
            image_filename="card1.png",
            upload_timestamp="2026-07-01 09:00:00",
            ocr_text="John Doe",
            structured_json={"name": "John Doe", "designation": "Dev", "company": "CloudScale", "phone": "123", "email": "j@c.com", "website": "c.com", "address": "Boston"},
            ocr_time=0.1,
            inference_time=0.1,
            total_time=0.2
        )
        
        # Verify User 2 cannot access User 1's card
        c_for_u2 = get_contact_by_hash(self.u2_id, h)
        self.assertIsNone(c_for_u2)
        
        all_u2_contacts = get_all_contacts(self.u2_id)
        self.assertEqual(len(all_u2_contacts), 0)
        
        # Verify composite uniqueness: User 2 CAN insert the same card independently
        u2_cid = insert_contact(
            user_id=self.u2_id,
            image_hash=h,
            image_filename="card1.png",
            upload_timestamp="2026-07-01 09:00:00",
            ocr_text="John Doe",
            structured_json={"name": "John Doe", "designation": "Dev", "company": "CloudScale", "phone": "123", "email": "j@c.com", "website": "c.com", "address": "Boston"},
            ocr_time=0.1,
            inference_time=0.1,
            total_time=0.2
        )
        self.assertIsNotNone(u2_cid)
        
        # Verify composite uniqueness: User 1 CANNOT insert the duplicate card again
        with self.assertRaises(DuplicateContactError):
            insert_contact(
                user_id=self.u1_id,
                image_hash=h,
                image_filename="card1_copy.png",
                upload_timestamp="2026-07-01 09:10:00",
                ocr_text="John Doe",
                structured_json={"name": "John Doe", "designation": "Dev", "company": "CloudScale", "phone": "123", "email": "j@c.com", "website": "c.com", "address": "Boston"},
                ocr_time=0.1,
                inference_time=0.1,
                total_time=0.2
            )

    def test_search_and_edit_contacts(self):
        cid = insert_contact(
            user_id=self.u1_id,
            image_hash="h1",
            image_filename="card1.png",
            upload_timestamp="2026-07-01 09:00:00",
            ocr_text="Alice Smith ApexTech",
            structured_json={"name": "Alice Smith", "designation": "VP", "company": "ApexTech", "phone": "555-1111", "email": "alice@apex.com", "website": "apex.com", "address": "SF"},
            ocr_time=0.1,
            inference_time=0.1,
            total_time=0.2
        )
        
        # Search check
        results = search_contacts(self.u1_id, "apextech")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["structured_json"]["name"], "Alice Smith")
        
        # Edit check
        updated_json = {"name": "Alice Jenkins", "designation": "CEO", "company": "ApexTech", "phone": "555-1111", "email": "alice@apex.com", "website": "apex.com", "address": "SF"}
        self.assertTrue(edit_contact(self.u1_id, cid, updated_json))
        
        contact = get_contact_by_hash(self.u1_id, "h1")
        self.assertEqual(contact["structured_json"]["name"], "Alice Jenkins")
        self.assertEqual(contact["structured_json"]["designation"], "CEO")

    def test_delete_contact(self):
        cid = insert_contact(
            user_id=self.u1_id,
            image_hash="delete_hash",
            image_filename="delete.png",
            upload_timestamp="2026-07-01",
            ocr_text="text",
            structured_json={"name": "A", "designation": "B", "company": "C", "phone": "1", "email": "a@c.com", "website": "c.com", "address": "Boston"},
            ocr_time=0.1,
            inference_time=0.1,
            total_time=0.2
        )
        
        # User 2 tries to delete User 1's card
        self.assertFalse(delete_contact(self.u2_id, cid))
        
        # User 1 deletes their own card
        self.assertTrue(delete_contact(self.u1_id, cid))
        self.assertIsNone(get_contact_by_hash(self.u1_id, "delete_hash"))

class TestRegexFallback(unittest.TestCase):
    
    def test_regex_fallback_extractor(self):
        ocr_text = """
        John Doe
        Software Architect
        CloudScale Solutions
        Phone: +1-555-0199
        Email: john.doe@cloudscale.com
        Web: www.cloudscale.com
        Address: 100 Innovation Way, Boston, MA 02110
        """
        data = regex_fallback_extractor(ocr_text)
        self.assertEqual(data["name"], "John Doe")
        self.assertEqual(data["designation"], "Software Architect")
        self.assertEqual(data["company"], "CloudScale Solutions")
        self.assertEqual(data["phone"], "+1-555-0199")
        self.assertEqual(data["email"], "john.doe@cloudscale.com")
        self.assertEqual(data["website"], "www.cloudscale.com")

if __name__ == "__main__":
    unittest.main()
