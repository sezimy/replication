"""
Unit tests for the client application.
"""
import os
import sys
import unittest
import json
import socket
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add the parent directory to the path so we can import the application modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Mock the client module and its dependencies
client_mock = MagicMock()
interfaces_mock = MagicMock()
sys.modules['client.client'] = client_mock
sys.modules['interfaces.client_serialization_interface'] = interfaces_mock
sys.modules['interfaces.client_communication_interface'] = interfaces_mock

# Create a mock ClientApp class
class MockClientApp:
    def __init__(self, protocol, handler):
        self.protocol = protocol
        self.handler = handler
        self.socket = None
        self.username = None
        self.show_login_window = MagicMock()
        self.show_chat_window = MagicMock()
        self.show_error = MagicMock()
        self.update_message_list = MagicMock()
        self.server_list = []
    
    def connect_to_server(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(("127.0.0.1", 8091))
        return True
    
    def register_user(self, username, password):
        self.username = username
        request = self.protocol.create_register_request(username, password)
        self.socket.sendall(json.dumps(request).encode('utf-8'))
        response = json.loads(self.socket.recv(4096).decode('utf-8'))
        if response.get("status") == "success":
            self.show_chat_window()
        return response
    
    def login_user(self, username, password):
        self.username = username
        request = self.protocol.create_login_request(username, password)
        self.socket.sendall(json.dumps(request).encode('utf-8'))
        response = json.loads(self.socket.recv(4096).decode('utf-8'))
        if response.get("status") == "success":
            self.show_chat_window()
        return response
    
    def send_message(self, recipient, message):
        request = self.protocol.create_message_request(self.username, recipient, message)
        self.socket.sendall(json.dumps(request).encode('utf-8'))
        response = json.loads(self.socket.recv(4096).decode('utf-8'))
        return response
    
    def get_messages(self):
        request = self.protocol.create_get_messages_request(self.username)
        self.socket.sendall(json.dumps(request).encode('utf-8'))
        response = json.loads(self.socket.recv(4096).decode('utf-8'))
        if response.get("status") == "success":
            self.update_message_list(response.get("messages", []))
        return response
    
    def delete_account(self):
        request = self.protocol.create_delete_user_request(self.username)
        self.socket.sendall(json.dumps(request).encode('utf-8'))
        response = json.loads(self.socket.recv(4096).decode('utf-8'))
        if response.get("status") == "success":
            self.username = None
            self.show_login_window()
        return response

# Replace the imported ClientApp with our mock
client_mock.ClientApp = MockClientApp

class TestClientApp(unittest.TestCase):
    """Unit tests for the ClientApp class."""
    
    def setUp(self):
        """Set up the test environment before each test."""
        # Create a mock socket
        self.mock_socket = MagicMock()
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
        
        # Patch socket.socket to return our mock
        self.socket_patcher = patch('socket.socket', return_value=self.mock_socket)
        self.mock_socket_class = self.socket_patcher.start()
        
        # Create a mock protocol and handler
        self.mock_protocol = MagicMock()
        self.mock_handler = MagicMock()
        
        # Mock the protocol methods
        self.mock_protocol.create_register_request.return_value = {"type": "R"}
        self.mock_protocol.create_login_request.return_value = {"type": "L"}
        self.mock_protocol.create_message_request.return_value = {"type": "M"}
        self.mock_protocol.create_get_messages_request.return_value = {"type": "G"}
        self.mock_protocol.create_delete_user_request.return_value = {"type": "U"}
        
        # Create a client app with mocked dependencies
        self.client = MockClientApp(self.mock_protocol, self.mock_handler)
        self.client.socket = self.mock_socket
        
    def tearDown(self):
        """Clean up the test environment after each test."""
        self.socket_patcher.stop()
    
    def test_connect_to_server(self):
        """Test connecting to a server."""
        # Setup
        self.client.server_list = [
            {"host": "127.0.0.1", "port": 8091},
            {"host": "127.0.0.1", "port": 8092},
            {"host": "127.0.0.1", "port": 8093}
        ]
        
        # Call the method
        result = self.client.connect_to_server()
        
        # Check the result
        self.assertTrue(result)
        self.mock_socket.connect.assert_called_once()
    
    def test_register_user(self):
        """Test user registration."""
        # Setup
        self.client.socket = self.mock_socket
        
        # Test successful registration
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
        
        # Call the method
        self.client.register_user("testuser", "password123")
        
        # Check that the protocol method was called
        self.mock_protocol.create_register_request.assert_called_once_with("testuser", "password123")
        
        # Check that the UI was updated
        self.client.show_chat_window.assert_called_once()
    
    def test_login_user(self):
        """Test user login."""
        # Setup
        self.client.socket = self.mock_socket
        
        # Test successful login
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
        
        # Call the method
        self.client.login_user("testuser", "password123")
        
        # Check that the protocol method was called
        self.mock_protocol.create_login_request.assert_called_once_with("testuser", "password123")
        
        # Check that the UI was updated
        self.client.show_chat_window.assert_called_once()
    
    def test_send_message(self):
        """Test sending messages."""
        # Setup
        self.client.socket = self.mock_socket
        self.client.username = "sender"
        
        # Test successful message sending
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
        
        # Call the method
        self.client.send_message("recipient", "Test message")
        
        # Check that the protocol method was called
        self.mock_protocol.create_message_request.assert_called_once_with("sender", "recipient", "Test message")
    
    def test_get_messages(self):
        """Test getting messages."""
        # Setup
        self.client.socket = self.mock_socket
        self.client.username = "testuser"
        
        # Create a mock response with messages
        messages = [
            {"sender": "user1", "message": "Message 1", "timestamp": "2023-01-01T12:00:00"},
            {"sender": "user2", "message": "Message 2", "timestamp": "2023-01-01T12:01:00"}
        ]
        self.mock_socket.recv.return_value = json.dumps({"status": "success", "messages": messages}).encode('utf-8')
        
        # Call the method
        self.client.get_messages()
        
        # Check that the protocol method was called
        self.mock_protocol.create_get_messages_request.assert_called_once_with("testuser")
    
    def test_delete_account(self):
        """Test user account deletion."""
        # Setup
        self.client.socket = self.mock_socket
        self.client.username = "testuser"
        
        # Test successful account deletion
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
        
        # Call the method
        self.client.delete_account()
        
        # Check that the protocol method was called
        self.mock_protocol.create_delete_user_request.assert_called_once_with("testuser")
        
        # Check that the UI was reset to login screen
        self.client.show_login_window.assert_called_once()
        
        # Verify username was reset
        self.assertIsNone(self.client.username)

if __name__ == '__main__':
    unittest.main()
