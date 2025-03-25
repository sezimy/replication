import unittest
from unittest.mock import Mock, patch
import socket
import struct
from backend.controller.routes import Controller, handle_client_messages
from backend.interactor.business_logic import BusinessLogic
from backend.database.mongo_operations import MongoOperation

class MockSocket:
    def __init__(self):
        self.sent_data = []
        self.recv_queue = []
        
    def sendall(self, data):
        self.sent_data.append(data)
        
    def recv(self, bufsize):
        if self.recv_queue:
            return self.recv_queue.pop(0)
        return b''
    
    def close(self):
        pass

class TestSocketConnection(unittest.TestCase):
    def setUp(self):
        self.mock_socket = MockSocket()
        self.business_logic = BusinessLogic(MongoOperation())
        self.controller = Controller(self.business_logic)
        
    def create_message(self, msg_type: str, payload: bytes) -> bytes:
        """Helper method to create wire protocol messages"""
        return struct.pack('!BI', ord(msg_type), len(payload)) + payload
        
    def test_register_user(self):
        # Create registration message
        username = "testuser"
        password = "testpass"
        payload = (
            struct.pack('!H', len(username)) + username.encode() +
            struct.pack('!H', len(password)) + password.encode()
        )
        message = self.create_message('R', payload)
        
        # Send message through mock socket
        response = self.controller.handle_incoming_message(message, self.mock_socket)
        
        # Check response
        msg_type = chr(response[0])
        payload_len = struct.unpack('!I', response[1:5])[0]
        response_message = response[5:5+payload_len].decode()
        
        self.assertEqual(msg_type, 'S')
        self.assertEqual(response_message, "User created successfully")
        
    def test_login_user(self):
        # First register a user
        username = "testuser"
        password = "testpass"
        reg_payload = (
            struct.pack('!H', len(username)) + username.encode() +
            struct.pack('!H', len(password)) + password.encode()
        )
        self.controller.handle_incoming_message(
            self.create_message('R', reg_payload),
            self.mock_socket
        )
        
        # Now try to login
        login_payload = (
            struct.pack('!H', len(username)) + username.encode() +
            struct.pack('!H', len(password)) + password.encode()
        )
        response = self.controller.handle_incoming_message(
            self.create_message('L', login_payload),
            self.mock_socket
        )
        
        # Check response
        msg_type = chr(response[0])
        payload_len = struct.unpack('!I', response[1:5])[0]
        response_message = response[5:5+payload_len].decode()
        
        self.assertEqual(msg_type, 'S')
        self.assertEqual(response_message, "Login successful")
        
    def test_send_message(self):
        # Register two users
        usernames = ["sender", "receiver"]
        password = "testpass"
        
        for username in usernames:
            reg_payload = (
                struct.pack('!H', len(username)) + username.encode() +
                struct.pack('!H', len(password)) + password.encode()
            )
            self.controller.handle_incoming_message(
                self.create_message('R', reg_payload),
                self.mock_socket
            )
            
        # Send a message
        message = "Hello, receiver!"
        msg_payload = (
            struct.pack('!H', len(usernames[0])) + usernames[0].encode() +
            struct.pack('!H', len(usernames[1])) + usernames[1].encode() +
            struct.pack('!I', len(message)) + message.encode()
        )
        
        response = self.controller.handle_incoming_message(
            self.create_message('M', msg_payload),
            self.mock_socket
        )
        
        # Check response
        msg_type = chr(response[0])
        payload_len = struct.unpack('!I', response[1:5])[0]
        response_message = response[5:5+payload_len].decode()
        
        self.assertEqual(msg_type, 'S')
        self.assertEqual(response_message, "Message sent")
        
    @patch('socket.socket')
    def test_client_connection(self, mock_socket):
        # Mock the socket connection
        mock_socket.return_value = self.mock_socket
        
        # Add test message to mock socket's receive queue
        username = "testuser"
        password = "testpass"
        payload = (
            struct.pack('!H', len(username)) + username.encode() +
            struct.pack('!H', len(password)) + password.encode()
        )
        self.mock_socket.recv_queue.append(self.create_message('R', payload))
        
        # Start client message handling
        handle_client_messages(self.mock_socket, ('127.0.0.1', 12345), self.controller)
        
        # Check that response was sent
        self.assertTrue(len(self.mock_socket.sent_data) > 0)
        response = self.mock_socket.sent_data[0]
        msg_type = chr(response[0])
        payload_len = struct.unpack('!I', response[1:5])[0]
        response_message = response[5:5+payload_len].decode()
        
        self.assertEqual(msg_type, 'S')
        self.assertEqual(response_message, "User created successfully")

if __name__ == '__main__':
    unittest.main() 