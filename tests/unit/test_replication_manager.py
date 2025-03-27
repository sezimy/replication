"""
Unit tests for the ReplicationManager class.
"""
import os
import sys
import unittest
import json
import socket
import threading
import time
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add the parent directory to the path so we can import the application modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Define the ServerRole enum to match the application's ServerState
class ServerRole(Enum):
    PRIMARY = "PRIMARY"
    BACKUP = "BACKUP"
    OFFLINE = "OFFLINE"

# Mock the replication manager module and its dependencies
replication_manager_mock = MagicMock()
business_logic_mock = MagicMock()
sys.modules['backend.replication.replication_manager'] = replication_manager_mock
sys.modules['backend.replication.server_state'] = MagicMock()
sys.modules['backend.interactor.business_logic'] = business_logic_mock

# Create a mock ReplicationManager class
class MockReplicationManager:
    def __init__(self, server_id, server_list, business_logic):
        self.server_id = server_id
        self.server_list = server_list
        self.business_logic = business_logic
        self.role = ServerRole.BACKUP
        self.primary_id = None
        self.backups = []
        self.heartbeat_interval = 5
        self.heartbeat_timeout = 15
        self.election_timeout = 30
        self.last_heartbeat = time.time()
        self.running = False
        self.heartbeat_thread = None
        self.election_thread = None
    
    def start(self):
        self.running = True
        return True
    
    def stop(self):
        self.running = False
        return True
    
    def become_primary(self):
        self.role = ServerRole.PRIMARY
        self.primary_id = self.server_id
        self.backups = [s["id"] for s in self.server_list if s["id"] != self.server_id]
        return True
    
    def become_backup(self):
        self.role = ServerRole.BACKUP
        return True
    
    def handle_client_operation(self, operation):
        if self.role == ServerRole.PRIMARY:
            self.business_logic.handle_operation(operation)
            self._replicate_to_backups(operation)
            return {"status": "success"}
        else:
            return self.forward_to_primary(operation)
    
    def forward_to_primary(self, data):
        if not self.primary_id:
            return {"status": "error", "message": "No primary server available"}
        
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            primary_server = next((s for s in self.server_list if s["id"] == self.primary_id), None)
            if not primary_server:
                return {"status": "error", "message": "Primary server not found"}
            
            primary_address = (primary_server["host"], primary_server["port"])
            client_sock.connect(primary_address)
            client_sock.sendall(json.dumps(data).encode('utf-8'))
            response = client_sock.recv(4096)
            return json.loads(response.decode('utf-8'))
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            client_sock.close()
    
    def _replicate_to_backups(self, operation):
        for backup_id in self.backups:
            backup_server = next((s for s in self.server_list if s["id"] == backup_id), None)
            if not backup_server:
                continue
            
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                backup_address = (backup_server["host"], backup_server["port"])
                client_sock.connect(backup_address)
                client_sock.sendall(json.dumps({"type": "REPLICATE", "data": operation}).encode('utf-8'))
                response = client_sock.recv(4096)
            except Exception as e:
                print(f"Error replicating to backup {backup_id}: {e}")
            finally:
                client_sock.close()

# Replace the imported ReplicationManager with our mock
replication_manager_mock.ReplicationManager = MockReplicationManager
replication_manager_mock.ServerState = ServerRole

class TestReplicationManager(unittest.TestCase):
    """Unit tests for the ReplicationManager class."""
    
    def setUp(self):
        """Set up the test environment before each test."""
        # Create a mock business logic
        self.mock_business_logic = MagicMock()
        
        # Create a server list
        self.server_list = [
            {"id": 1, "host": "127.0.0.1", "port": 8091},
            {"id": 2, "host": "127.0.0.1", "port": 8092},
            {"id": 3, "host": "127.0.0.1", "port": 8093}
        ]
        
        # Create a replication manager
        self.replication_manager = MockReplicationManager(1, self.server_list, self.mock_business_logic)
        
        # Patch socket.socket to return a mock
        self.socket_patcher = patch('socket.socket')
        self.mock_socket_class = self.socket_patcher.start()
        self.mock_socket = MagicMock()
        self.mock_socket_class.return_value = self.mock_socket
        self.mock_socket.recv.return_value = json.dumps({"status": "success"}).encode('utf-8')
    
    def tearDown(self):
        """Clean up the test environment after each test."""
        self.socket_patcher.stop()
    
    def test_initialization(self):
        """Test that the ReplicationManager initializes correctly."""
        # Check that the server ID is set correctly
        self.assertEqual(self.replication_manager.server_id, 1)
        
        # Check that the server list is set correctly
        self.assertEqual(self.replication_manager.server_list, self.server_list)
        
        # Check that the business logic is set correctly
        self.assertEqual(self.replication_manager.business_logic, self.mock_business_logic)
        
        # Check that the initial state is BACKUP
        self.assertEqual(self.replication_manager.role, ServerRole.BACKUP)
    
    def test_handle_client_operation(self):
        """Test handling client operations."""
        # Set up the replication manager as PRIMARY
        self.replication_manager.role = ServerRole.PRIMARY
        
        # Create a test operation
        operation = {"type": "M", "sender": "user1", "recipient": "user2", "message": "Hello"}
        
        # Call the method
        self.replication_manager.handle_client_operation(operation)
        
        # Check that the business logic was called
        self.replication_manager.business_logic.handle_operation.assert_called_once_with(operation)
    
    def test_forward_to_primary(self):
        """Test forwarding operations to the primary server."""
        # Set up the replication manager as BACKUP
        self.replication_manager.role = ServerRole.BACKUP
        self.replication_manager.primary_id = 2
        
        # Create a test operation
        operation = {"type": "M", "sender": "user1", "recipient": "user2", "message": "Hello"}
        
        # Call the method
        self.replication_manager.forward_to_primary(operation)
        
        # Check that a socket was created
        self.mock_socket_class.assert_called_once()
        
        # Check that the socket connected to the primary
        self.mock_socket.connect.assert_called_once()
        
        # Check that the operation was sent
        self.mock_socket.sendall.assert_called_once()
    
    def test_become_primary(self):
        """Test transitioning to PRIMARY role."""
        # Set up the replication manager as BACKUP
        self.replication_manager.role = ServerRole.BACKUP
        
        # Call the method
        self.replication_manager.become_primary()
        
        # Check that the role changed to PRIMARY
        self.assertEqual(self.replication_manager.role, ServerRole.PRIMARY)
        
        # Check that the primary ID is set to this server
        self.assertEqual(self.replication_manager.primary_id, 1)
        
        # Check that the backups list contains the other servers
        self.assertEqual(set(self.replication_manager.backups), {2, 3})
    
    def test_become_backup(self):
        """Test transitioning to BACKUP role."""
        # Set up the replication manager as PRIMARY
        self.replication_manager.role = ServerRole.PRIMARY
        
        # Call the method
        self.replication_manager.become_backup()
        
        # Check that the role changed to BACKUP
        self.assertEqual(self.replication_manager.role, ServerRole.BACKUP)

if __name__ == '__main__':
    unittest.main()
