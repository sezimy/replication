import unittest
import json
import socket
import threading
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from protocol.client_rpc_protocol import ClientRpcProtocol
from network.client_rpc_handler import ClientRpcHandler

class MockSocket:
    """Mock socket for testing network communication"""
    def __init__(self):
        self.sent_data = []
        self.responses = []
    
    def send(self, data):
        self.sent_data.append(data)
        return self.responses.pop(0)
    
    def recv(self, size):
        if self.responses:
            return self.responses.pop(0)
        return b''
    
    def add_response(self, response):
        self.responses.append(json.dumps(response).encode('utf-8'))

class MockRpcHandler(ClientRpcHandler):
    def __init__(self, mock_socket):
        super().__init__()
        self.mock_socket = mock_socket
        
    def send_message(self, data):
        return json.loads(self.mock_socket.send(data).decode('utf-8'))

class TestRPCIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_socket = MockSocket()
        self.rpc = ClientRpcProtocol()
        self.handler = MockRpcHandler(self.mock_socket)
        self.test_data = {
            'username': 'testuser',
            'password': 'TestPass123!',
            'message': 'Hello, World!',
            'recipient': 'user2'
        }

    def test_login_success(self):
        """Test successful login flow"""
        # Prepare request
        login_data = self.rpc.serialize_message('L', [
            self.test_data['username'],
            self.test_data['password']
        ])
        
        # Mock successful response
        self.mock_socket.add_response({
            'jsonrpc': '2.0',
            'result': {'type': 'S', 'payload': 'Login successful'},
            'id': 1
        })
        
        # Send request
        response = self.handler.send_message(login_data)
        
        # Verify response
        self.assertEqual(response['result']['type'], 'S')
        print(f"\nLogin request size: {len(login_data)} bytes")

    def test_login_failure(self):
        """Test failed login flow"""
        login_data = self.rpc.serialize_message('L', [
            self.test_data['username'],
            'wrong_password'
        ])
        
        self.mock_socket.add_response({
            'jsonrpc': '2.0',
            'error': {'code': -32001, 'message': 'Invalid credentials'},
            'id': 1
        })
        
        response = self.handler.send_message(login_data)
        self.assertIn('error', response)

    def test_message_sending(self):
        """Test message sending flow"""
        message_data = self.rpc.serialize_message('M', [
            self.test_data['username'],
            self.test_data['recipient'],
            self.test_data['message']
        ])
        
        self.mock_socket.add_response({
            'jsonrpc': '2.0',
            'result': {'type': 'S', 'payload': 'Message sent'},
            'id': 1
        })
        
        response = self.handler.send_message(message_data)
        self.assertEqual(response['result']['type'], 'S')
        print(f"Message request size: {len(message_data)} bytes")

    def test_concurrent_messages(self):
        """Test handling multiple messages concurrently"""
        message_count = 3
        responses = []
        
        def send_message(i):
            data = self.rpc.serialize_message('M', [
                self.test_data['username'],
                self.test_data['recipient'],
                f"Message {i}"
            ])
            self.mock_socket.add_response({
                'jsonrpc': '2.0',
                'result': {'type': 'S', 'payload': f'Message {i} sent'},
                'id': i + 1
            })
            response = self.handler.send_message(data)
            responses.append(response)
        
        threads = []
        for i in range(message_count):
            thread = threading.Thread(target=send_message, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        self.assertEqual(len(responses), message_count)
        for i, response in enumerate(responses):
            self.assertEqual(response['result']['type'], 'S')

if __name__ == '__main__':
    unittest.main()
