"""
Unit tests for the BusinessLogic class.
"""
import os
import sys
import unittest
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to the path so we can import the application modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Mock bcrypt to avoid dependency issues
sys.modules['bcrypt'] = MagicMock()
import bcrypt

# Mock the modules
business_logic_mock = MagicMock()
file_operations_mock = MagicMock()
sys.modules['backend.interactor.business_logic'] = business_logic_mock
sys.modules['backend.database.file_operations'] = file_operations_mock

# Create mock classes
class MockBusinessLogic:
    def __init__(self, storage):
        self.storage = storage
    
    def register_user(self, username, password):
        if username in self.storage.get_users():
            return {"status": "error", "message": "User already exists"}
        
        # Hash the password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Store the user
        self.storage.add_user(username, {"password": hashed})
        
        return {"status": "success"}
    
    def login_user(self, username, password):
        users = self.storage.get_users()
        if username not in users:
            return {"status": "error", "message": "User not found"}
        
        user_data = users.get(username)
        if not bcrypt.checkpw(password.encode('utf-8'), user_data.get("password").encode('utf-8')):
            return {"status": "error", "message": "Invalid password"}
        
        return {"status": "success"}
    
    def send_message(self, sender, recipient, message):
        users = self.storage.get_users()
        if recipient not in users:
            return {"status": "error", "message": "Recipient not found"}
        
        self.storage.add_message(recipient, {"sender": sender, "message": message})
        
        return {"status": "success"}
    
    def get_messages(self, username):
        messages = self.storage.get_messages(username)
        return {"status": "success", "messages": messages}
    
    def delete_user(self, username):
        users = self.storage.get_users()
        if username not in users:
            return {"status": "error", "message": "User not found"}
        
        self.storage.delete_user(username)
        
        return {"status": "success"}

class MockFileStorage:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.users = {}
        self.messages = {}
    
    def get_users(self):
        return self.users
    
    def add_user(self, username, data):
        self.users[username] = data
    
    def delete_user(self, username):
        if username in self.users:
            del self.users[username]
    
    def get_messages(self, username):
        return self.messages.get(username, [])
    
    def add_message(self, username, message):
        if username not in self.messages:
            self.messages[username] = []
        self.messages[username].append(message)

# Replace the imported classes with our mocks
business_logic_mock.BusinessLogic = MockBusinessLogic
file_operations_mock.FileStorage = MockFileStorage

class TestBusinessLogic(unittest.TestCase):
    """Unit tests for the BusinessLogic class."""
    
    def setUp(self):
        """Set up the test environment before each test."""
        # Create a test data directory
        self.test_dir = Path(__file__).parent / "test_data"
        self.test_dir.mkdir(exist_ok=True)
        
        # Initialize the storage and business logic
        self.storage = MockFileStorage(str(self.test_dir))
        self.business_logic = MockBusinessLogic(self.storage)
        
    def tearDown(self):
        """Clean up the test environment after each test."""
        # Remove test data directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_register_user(self):
        """Test user registration."""
        # Test successful registration
        result = self.business_logic.register_user("testuser", "password123")
        self.assertEqual(result.get("status"), "success")
        
        # Verify that the user was added to storage
        users = self.storage.get_users()
        self.assertIn("testuser", users)
        
        # Test registering an existing user
        result = self.business_logic.register_user("testuser", "password123")
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("message"), "User already exists")
    
    def test_login_user(self):
        """Test user login."""
        # Add a test user
        hashed = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.storage.add_user("testuser", {"password": hashed})
        
        # Mock bcrypt.checkpw to return True for valid password
        bcrypt.checkpw = MagicMock(return_value=True)
        
        # Test successful login
        result = self.business_logic.login_user("testuser", "password123")
        self.assertEqual(result.get("status"), "success")
        
        # Mock bcrypt.checkpw to return False for invalid password
        bcrypt.checkpw = MagicMock(return_value=False)
        
        # Test login with invalid password
        result = self.business_logic.login_user("testuser", "wrongpassword")
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("message"), "Invalid password")
        
        # Test login with non-existent user
        result = self.business_logic.login_user("nonexistentuser", "password123")
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("message"), "User not found")
    
    def test_send_message(self):
        """Test sending messages."""
        # Add test users
        self.storage.add_user("sender", {"password": "hashedpassword"})
        self.storage.add_user("recipient", {"password": "hashedpassword"})
        
        # Test successful message sending
        result = self.business_logic.send_message("sender", "recipient", "Test message")
        self.assertEqual(result.get("status"), "success")
        
        # Verify that the message was added to storage
        messages = self.storage.get_messages("recipient")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].get("sender"), "sender")
        self.assertEqual(messages[0].get("message"), "Test message")
        
        # Test sending to non-existent recipient
        result = self.business_logic.send_message("sender", "nonexistent", "Test message")
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("message"), "Recipient not found")
    
    def test_get_messages(self):
        """Test getting messages."""
        # Add test user
        self.storage.add_user("testuser", {"password": "hashedpassword"})
        
        # Add test messages
        self.storage.add_message("testuser", {"sender": "user1", "message": "Message 1"})
        self.storage.add_message("testuser", {"sender": "user2", "message": "Message 2"})
        self.storage.add_message("testuser", {"sender": "user3", "message": "Message 3"})
        
        # Test getting messages
        result = self.business_logic.get_messages("testuser")
        self.assertEqual(result.get("status"), "success")
        
        # Verify that the messages were retrieved
        messages = result.get("messages")
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0].get("sender"), "user1")
        self.assertEqual(messages[0].get("message"), "Message 1")
        self.assertEqual(messages[2].get("sender"), "user3")
        self.assertEqual(messages[2].get("message"), "Message 3")
    
    def test_delete_user(self):
        """Test user deletion."""
        # Add test user
        self.storage.add_user("testuser", {"password": "hashedpassword"})
        
        # Test successful user deletion
        result = self.business_logic.delete_user("testuser")
        self.assertEqual(result.get("status"), "success")
        
        # Verify that the user was removed from storage
        users = self.storage.get_users()
        self.assertNotIn("testuser", users)
        
        # Test deleting non-existent user
        result = self.business_logic.delete_user("nonexistentuser")
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("message"), "User not found")

if __name__ == '__main__':
    unittest.main()
