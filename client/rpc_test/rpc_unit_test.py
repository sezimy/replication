import unittest
import json
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from protocol.client_rpc_protocol import ClientRpcProtocol

class TestRPCUnit(unittest.TestCase):
    def setUp(self):
        self.rpc = ClientRpcProtocol()
        self.test_data = {
            'username': 'testuser',
            'password': 'TestPass123!',
            'message': 'Hello, World!',
            'recipient': 'user2',
            'timestamp': '2025-02-25T22:00:00'  # Use string timestamp instead of datetime
        }

    def test_login_format(self):
        """Test login message format"""
        data = self.rpc.serialize_message('L', [self.test_data['username'], self.test_data['password']])
        decoded = json.loads(data.decode('utf-8'))
        
        # Verify RPC structure
        self.assertEqual(decoded['jsonrpc'], '2.0')
        self.assertEqual(decoded['params']['type'], 'L')
        self.assertEqual(decoded['params']['username'], self.test_data['username'])
        
        # Print size for analysis
        print(f"\nLogin message size: {len(data)} bytes")

    def test_chat_message_format(self):
        """Test chat message format"""
        data = self.rpc.serialize_message('M', [
            self.test_data['username'],
            self.test_data['recipient'],
            self.test_data['message']
        ])
        decoded = json.loads(data.decode('utf-8'))
        
        self.assertEqual(decoded['params']['type'], 'M')
        self.assertEqual(decoded['params']['sender'], self.test_data['username'])
        self.assertEqual(decoded['params']['message'], self.test_data['message'])
        
        print(f"Chat message size: {len(data)} bytes")

    def test_delete_message_format(self):
        """Test delete message format"""
        data = self.rpc.serialize_message('D', [
            self.test_data['message'],
            self.test_data['timestamp'],
            self.test_data['username'],
            self.test_data['recipient']
        ])
        decoded = json.loads(data.decode('utf-8'))
        
        self.assertEqual(decoded['params']['type'], 'D')
        self.assertEqual(decoded['params']['message'], self.test_data['message'])
        self.assertEqual(decoded['params']['sender'], self.test_data['username'])
        
        print(f"Delete message size: {len(data)} bytes")

    def test_message_consistency(self):
        """Test that same input produces same output"""
        msg1 = self.rpc.serialize_message('M', [
            self.test_data['username'],
            self.test_data['recipient'],
            self.test_data['message']
        ])
        msg2 = self.rpc.serialize_message('M', [
            self.test_data['username'],
            self.test_data['recipient'],
            self.test_data['message']
        ])
        
        self.assertEqual(msg1, msg2)

if __name__ == '__main__':
    unittest.main()
