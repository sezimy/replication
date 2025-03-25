import unittest
import sys
import os
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.interactor.business_logic import BusinessLogic
from backend.database.mongo_operations import MongoOperation

class TestBusinessLogic(unittest.TestCase):
    def setUp(self):
        self.mongo_ops = MongoOperation()
        self.business_logic = BusinessLogic(self.mongo_ops)
        # Clear test data before each test
        self.mongo_ops.delete("users", {})
        self.mongo_ops.delete("messages", {})

    def test_create_user(self):
        # Test creating a new user
        result = self.business_logic.create_user("test_user", "test_pass")
        self.assertTrue(result)

        # Verify user was created
        user = self.business_logic.get_user("test_user")
        self.assertTrue(len(user) > 0)
        self.assertEqual(user[0]["user_name"], "test_user")
        self.assertEqual(user[0]["user_password"], "test_pass")
        self.assertEqual(user[0]["view_count"], 5)  # Default view count

    def test_delete_user(self):
        # Create user first
        self.business_logic.create_user("delete_test", "test_pass")
        
        # Test deletion
        result = self.business_logic.delete_user("delete_test")
        self.assertTrue(result)

        # Verify user was deleted
        user = self.business_logic.get_user("delete_test")
        self.assertEqual(len(user), 0)

    def test_get_all_users(self):
        # Create multiple test users
        self.business_logic.create_user("user1", "pass1")
        self.business_logic.create_user("user2", "pass2")
        
        users = self.business_logic.get_all_users()
        self.assertEqual(len(users), 2)
        self.assertIn("user1", users)
        self.assertIn("user2", users)

    def test_login_user(self):
        # Create test user
        self.business_logic.create_user("login_test", "correct_pass")
        
        # Test successful login
        result = self.business_logic.login_user("login_test", "correct_pass")
        self.assertTrue(result)
        
        # Test failed login with wrong password
        result = self.business_logic.login_user("login_test", "wrong_pass")
        self.assertFalse(result)
        
        # Test login with non-existent user
        result = self.business_logic.login_user("nonexistent", "pass")
        self.assertFalse(result)

    def test_send_and_get_messages(self):
        # Create test users
        self.business_logic.create_user("sender", "pass")
        self.business_logic.create_user("receiver", "pass")
        
        # Test sending message
        result = self.business_logic.send_message("sender", "receiver", "Hello!")
        self.assertTrue(result)
        
        # Test getting messages
        messages = self.business_logic.get_messages("sender")
        self.assertIn("receiver", messages)
        self.assertEqual(len(messages["receiver"]), 1)
        self.assertEqual(messages["receiver"][0]["message"], "Hello!")
        
        # Test receiver's view
        receiver_messages = self.business_logic.get_messages("receiver")
        self.assertIn("sender", receiver_messages)
        self.assertEqual(receiver_messages["sender"][0]["message"], "Hello!")

    def test_delete_message(self):
        # Create users and send message
        self.business_logic.create_user("user1", "pass")
        self.business_logic.create_user("user2", "pass")
        self.business_logic.send_message("user1", "user2", "Test message")
        
        # Get message details
        messages = self.business_logic.get_messages("user1")
        message = messages["user2"][0]
        timestamp = message["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        
        # Test message deletion
        result = self.business_logic.delete_message(
            "Test message", 
            timestamp,
            "user1",
            "user2"
        )
        self.assertTrue(result)
        
        # Verify message was deleted
        updated_messages = self.business_logic.get_messages("user1")
        self.assertEqual(len(updated_messages.get("user2", [])), 0)

if __name__ == '__main__':
    unittest.main()
