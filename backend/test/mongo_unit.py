import unittest
import sys
import os
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.database.mongo_operations import MongoOperation

class TestMongoOperations(unittest.TestCase):
    def setUp(self):
        self.mongo_ops = MongoOperation()
        # Clear test data before each test
        self.mongo_ops.delete("users", {})
        self.mongo_ops.delete("messages", {})

    def test_insert_and_read_user(self):
        # Test inserting a user
        test_user = {
            "user_name": "test_user",
            "user_password": "test_pass"
        }
        result = self.mongo_ops.insert("users", test_user)
        self.assertTrue(result)

        # Test reading the user back
        query = {"user_name": "test_user"}
        read_result = self.mongo_ops.read("users", query)
        self.assertIsNotNone(read_result)
        self.assertEqual(len(read_result), 1)
        self.assertEqual(read_result[0]["user_name"], "test_user")
        self.assertEqual(read_result[0]["user_password"], "test_pass")

    def test_insert_and_read_message(self):
        # Test inserting a message
        test_message = {
            "sender": "user1",
            "receiver": "user2",
            "message": "Hello!",
            "timestamp": datetime.now()
        }
        result = self.mongo_ops.insert("messages", test_message)
        self.assertTrue(result)

        # Test reading the message back
        query = {"sender": "user1", "receiver": "user2"}
        read_result = self.mongo_ops.read("messages", query)
        self.assertIsNotNone(read_result)
        self.assertEqual(len(read_result), 1)
        self.assertEqual(read_result[0]["message"], "Hello!")

    def test_delete_user(self):
        # Insert a test user first
        test_user = {
            "user_name": "delete_test",
            "user_password": "test_pass"
        }
        self.mongo_ops.insert("users", test_user)

        # Test deleting the user
        query = {"user_name": "delete_test"}
        delete_result = self.mongo_ops.delete("users", query)
        self.assertEqual(delete_result, 1)

        # Verify user is deleted
        read_result = self.mongo_ops.read("users", query)
        self.assertEqual(len(read_result), 0)

    def test_update_user(self):
        # Insert a test user first
        test_user = {
            "user_name": "update_test",
            "user_password": "old_pass"
        }
        self.mongo_ops.insert("users", test_user)

        # Test updating the user
        query = {"user_name": "update_test"}
        update_values = {"user_password": "new_pass"}
        update_result = self.mongo_ops.update("users", query, update_values)
        self.assertEqual(update_result, 1)

        # Verify update
        read_result = self.mongo_ops.read("users", query)
        self.assertEqual(read_result[0]["user_password"], "new_pass")

if __name__ == '__main__':
    unittest.main()
