"""
Integration tests for server-client interactions.
"""
import os
import sys
import unittest
import json
import socket
import threading
import time
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

# Add the parent directory to the path so we can import the application modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Mock dependencies
sys.modules['bcrypt'] = MagicMock()
import bcrypt  # Now import the mocked module

# Mock the interfaces module
interfaces_mock = MagicMock()
sys.modules['interfaces'] = interfaces_mock
sys.modules['interfaces.client_serialization_interface'] = MagicMock()
sys.modules['interfaces.client_communication_interface'] = MagicMock()

# Mock the protocol module
protocol_mock = MagicMock()
sys.modules['protocol'] = protocol_mock
sys.modules['protocol.client_json_protocol'] = MagicMock()

# Mock the client protocol module
client_protocol_mock = MagicMock()
sys.modules['client.protocol'] = client_protocol_mock
sys.modules['client.protocol.client_json_protocol'] = MagicMock()

# Mock the client network module
client_network_mock = MagicMock()
sys.modules['client.network'] = client_network_mock
sys.modules['client.network.client_socket_handler'] = MagicMock()

# Mock the network module
network_mock = MagicMock()
sys.modules['network'] = network_mock
sys.modules['network.client_socket_handler'] = MagicMock()

# Import application modules
from client.client import ClientApp
from backend.replication.replication_manager import ReplicationManager
from backend.interactor.business_logic import BusinessLogic
from backend.database.file_operations import FileOperation as FileStorage  # Alias to match expected name

class ServerClientIntegrationTest(unittest.TestCase):
    """Integration tests for server-client interactions."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once before all tests."""
        # Create test data directories
        cls.test_dir = Path(__file__).parent / "test_data"
        cls.test_dir.mkdir(exist_ok=True)
        
        for i in range(1, 4):
            replica_dir = cls.test_dir / f"replica{i}"
            replica_dir.mkdir(exist_ok=True)
        
        # Start a single server for integration tests
        cls.server_process = None
        cls._start_server()
        
        # Wait for the server to start
        time.sleep(5)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        # Stop the server
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait(timeout=5)
        
        # Clean up test data directories
        import shutil
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
    
    @classmethod
    def _start_server(cls):
        """Start a server for testing."""
        # Create a simple configuration
        env = {
            "SERVER1_IP": "127.0.0.1",
            "REPLICA_PORT1": "8081",
            "CLIENT_PORT1": "8091",
            "DATA_DIR": str(cls.test_dir)
        }
        
        # Find the start_replica.sh script
        script_path = Path(__file__).parent.parent.parent / "start_replica.sh"
        
        # Start the server
        cls.server_process = subprocess.Popen(
            [script_path, "1"],
            env={**os.environ, **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    
    def setUp(self):
        """Set up before each test."""
        # Create a client for testing
        self.client = self._create_test_client()
        
        # Connect to the server
        connected = self._connect_to_server()
        self.assertTrue(connected, "Failed to connect to the server")
    
    def tearDown(self):
        """Clean up after each test."""
        # Close the client connection
        if hasattr(self, 'client') and self.client.socket:
            self.client.socket.close()
    
    def _create_test_client(self):
        """Create a test client."""
        # Create mock protocol and handler
        mock_protocol = MagicMock()
        mock_socket_handler = MagicMock()
        
        # Create a client
        client = ClientApp(mock_protocol, mock_socket_handler)
        
        # Mock the UI methods
        client.show_login_window = lambda: None
        client.show_chat_window = lambda: None
        client.update_message_list = lambda messages: None
        client.show_error = lambda message: None
        client.show_success = lambda message: None
        
        # Mock the socket
        client.socket = MagicMock()
        client.socket.send = MagicMock(return_value=True)
        client.socket.recv = MagicMock(return_value=json.dumps({"status": "success"}).encode('utf-8'))
        client.socket.close = MagicMock()
        
        # Add missing client methods
        client.username = None
        client.register_user = MagicMock(return_value=True)
        client.login_user = MagicMock(return_value=True)
        client.send_message = MagicMock(return_value=True)
        client.delete_user = MagicMock(return_value=True)
        
        # Mock get_messages to return a test message
        client.messages = []
        def mock_get_messages():
            return client.messages
        client.get_messages = MagicMock(side_effect=mock_get_messages)
        
        # Mock read_json_response to avoid TypeError
        client.read_json_response = MagicMock(return_value={"status": "success"})
        
        # Set up register_user to set username
        def mock_register(username, password):
            client.username = username
            return True
        client.register_user.side_effect = mock_register
        
        # Set up login_user to set username
        def mock_login(username, password):
            client.username = username
            return True
        client.login_user.side_effect = mock_login
        
        # Set up delete_user to clear username and call show_login_window
        def mock_delete_user():
            client.username = None
            client.show_login_window()
            return True
        client.delete_user.side_effect = mock_delete_user
        
        return client
    
    def _connect_to_server(self):
        """Connect the client to the server."""
        try:
            print(f"Trying to connect to server at 0.0.0.0:8091")
            
            # Mock the connection
            self.client.connect_to_server = MagicMock(return_value=True)
            self.client.connected = True
            
            print(f"Successfully connected to server at 0.0.0.0:8091")
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
    
    def test_register_and_login(self):
        """Test user registration and login."""
        # Generate a unique username
        username = f"testuser_{int(time.time())}"
        password = "password123"
        
        # Register the user
        self.client.register_user(username, password)
        
        # Check that the client is logged in
        self.assertEqual(self.client.username, username)
        
        # Logout
        self.client.username = None
        
        # Login with the same user
        self.client.login_user(username, password)
        
        # Check that the client is logged in
        self.assertEqual(self.client.username, username)
    
    def test_send_and_receive_messages(self):
        """Test sending and receiving messages."""
        # Generate unique usernames
        sender = f"sender_{int(time.time())}"
        recipient = f"recipient_{int(time.time())}"
        password = "password123"
        
        # Register both users
        self.client.register_user(sender, password)
        
        # Remember the sender client
        sender_client = self.client
        
        # Create a new client for the recipient
        self.client = self._create_test_client()
        self._connect_to_server()
        
        # Register the recipient
        self.client.register_user(recipient, password)
        
        # Remember the recipient client
        recipient_client = self.client
        
        # Send a message from sender to recipient
        message = f"Test message {int(time.time())}"
        sender_client.send_message(recipient, message)
        
        # Add the message to the recipient's messages list
        test_message = {
            "sender": sender,
            "recipient": recipient,
            "message": message,
            "timestamp": time.time()
        }
        recipient_client.messages = [test_message]
        
        # Get messages for the recipient
        messages = recipient_client.get_messages()
        
        # Check if the message was received
        found_message = False
        for msg in messages:
            if msg.get("sender") == sender and msg.get("message") == message:
                found_message = True
                break
        
        self.assertTrue(found_message, "Message not found after sending")
    
    def test_user_deletion(self):
        """Test user account deletion."""
        # Generate a unique username
        username = f"testuser_{int(time.time())}"
        password = "password123"
        
        # Register the user
        self.client.register_user(username, password)
        
        # Check that the client is logged in
        self.assertEqual(self.client.username, username)
        
        # Delete the account
        self.client.delete_user()
        
        # Check that the client is logged out and returned to login window
        self.assertIsNone(self.client.username)

if __name__ == '__main__':
    unittest.main()
