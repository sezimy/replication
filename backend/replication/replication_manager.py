import socket
import threading
import time
import json
import os
import sys
import random
from enum import Enum
from typing import List, Dict, Callable, Optional, Tuple

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

class ServerRole(Enum):
    PRIMARY = "PRIMARY"
    BACKUP = "BACKUP"
    CANDIDATE = "CANDIDATE"

class ReplicationManager:
    """
    Manages replication between multiple server instances for fault tolerance.
    Implements a primary-backup replication scheme with leader election.
    """
    
    def __init__(self, server_id: str, data_dir: str, replica_addresses: List[Tuple[str, int]], 
                 local_address: Tuple[str, int], client_handler: Callable):
        """
        Initialize the replication manager.
        
        Args:
            server_id: Unique identifier for this server
            data_dir: Directory where this server's data files are stored
            replica_addresses: List of (host, port) tuples for all replicas in the system
            local_address: (host, port) tuple for this server's replication endpoint
            client_handler: Function to handle client requests
        """
        self.server_id = server_id
        self.data_dir = data_dir
        self.replica_addresses = replica_addresses
        self.local_address = local_address
        self.client_handler = client_handler
        
        # Server state
        self.role = ServerRole.CANDIDATE
        self.primary_id = None
        self.current_term = 0  # Election term
        self.voted_for = None
        self.active_replicas = set()
        
        # Communication sockets
        self.replication_socket = None
        self.client_socket = None
        
        # Locks for thread safety
        self.state_lock = threading.Lock()
        self.vote_lock = threading.Lock()
        
        # Threads
        self.heartbeat_thread = None
        self.election_thread = None
        self.replication_listener_thread = None
        self.running = False
        
        # Operation log for replication
        self.operation_log = []
        self.log_lock = threading.Lock()
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
    def start(self):
        """Start the replication manager and all its threads."""
        self.running = True
        
        # Start replication listener
        self.replication_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.replication_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.replication_socket.bind(self.local_address)
        self.replication_socket.listen(10)
        
        self.replication_listener_thread = threading.Thread(target=self._replication_listener)
        self.replication_listener_thread.daemon = True
        self.replication_listener_thread.start()
        
        # Start an election immediately
        self._start_election()
        
        # Wait for election to complete (up to 5 seconds)
        election_timeout = 5
        start_time = time.time()
        while time.time() - start_time < election_timeout:
            with self.state_lock:
                if self.role == ServerRole.PRIMARY or self.primary_id is not None:
                    print(f"Election completed. Role: {self.role}, Primary: {self.primary_id}")
                    break
            time.sleep(0.1)
        
        # If no primary was elected, become primary
        with self.state_lock:
            if self.role != ServerRole.PRIMARY and self.primary_id is None:
                print(f"No primary elected after timeout. Server {self.server_id} becoming PRIMARY.")
                self.role = ServerRole.PRIMARY
                self.primary_id = self.server_id
                self.current_term += 1
                print(f"Server {self.server_id} elected as PRIMARY for term {self.current_term}")
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        # Start election timeout thread
        self.election_thread = threading.Thread(target=self._election_timeout_loop)
        self.election_thread.daemon = True
        self.election_thread.start()
        
    def stop(self):
        """Stop the replication manager and all its threads."""
        self.running = False
        if self.replication_socket:
            self.replication_socket.close()
    
    def handle_client_operation(self, operation_type: str, data: bytes) -> bytes:
        """
        Handle a client operation, possibly forwarding to the primary.
        
        Args:
            operation_type: Type of operation (read or write)
            data: Operation data
            
        Returns:
            Response bytes to send back to the client
        """
        print(f"ReplicationManager: Handling {operation_type} operation")
        
        with self.state_lock:
            # If this server is the primary, process the operation
            if self.role == ServerRole.PRIMARY:
                print(f"ReplicationManager: This server ({self.server_id}) is PRIMARY, processing locally")
                # Process the operation locally
                try:
                    # Extract the message type for logging
                    try:
                        msg_type = data.decode('utf-8')[2:3]  # Usually the message type is at position 2
                        print(f"ReplicationManager: Processing operation of type '{msg_type}'")
                    except:
                        print("ReplicationManager: Could not extract message type")
                    
                    response = self.client_handler(data, None)
                    
                    # For write operations, replicate to backups
                    if self._is_write_operation(data):
                        print("ReplicationManager: This is a write operation, replicating to backups")
                        self._replicate_operation(data)
                    
                    print(f"ReplicationManager: Operation processed successfully, response length: {len(response) if response else 0}")
                    return response
                except Exception as e:
                    print(f"ReplicationManager: Error processing operation: {e}")
                    import traceback
                    traceback.print_exc()
                    error_response = {"type": "E", "payload": f"Error processing request: {str(e)}"}
                    return json.dumps([error_response]).encode('utf-8')
            
            # If this server knows who the primary is, forward the request
            elif self.primary_id is not None:
                print(f"ReplicationManager: This server is BACKUP, forwarding to PRIMARY ({self.primary_id})")
                # Find the primary's address
                primary_address = None
                for replica in self.replica_addresses:
                    if self._get_server_id_from_address(replica) == self.primary_id:
                        primary_address = replica
                        break
                
                if primary_address:
                    # Forward the request to the primary
                    try:
                        print(f"ReplicationManager: Forwarding request to primary at {primary_address}")
                        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        client_sock.settimeout(5)  # 5 second timeout
                        client_sock.connect(primary_address)
                        client_sock.sendall(data)
                        response = client_sock.recv(4096)
                        client_sock.close()
                        print(f"ReplicationManager: Received response from primary, length: {len(response)}")
                        return response
                    except Exception as e:
                        print(f"ReplicationManager: Error forwarding to primary: {e}")
                        # Primary might be down, start a new election
                        self._start_election()
                        # Return error to client
                        error_response = {"type": "E", "payload": "Primary server unavailable, trying to elect new primary"}
                        return json.dumps([error_response]).encode('utf-8')
            
            # If we don't know who the primary is, return an error
            print("ReplicationManager: No primary server available")
            error_response = {"type": "E", "payload": "No primary server available"}
            return json.dumps([error_response]).encode('utf-8')
    
    def _is_write_operation(self, data: bytes) -> bool:
        """
        Determine if an operation is a write operation that needs to be replicated.
        
        Args:
            data: Operation data
            
        Returns:
            True if this is a write operation, False otherwise
        """
        try:
            json_data = json.loads(data.decode('utf-8'))
            msg_type = json_data.get('type', '')
            
            # These operations modify server state
            write_types = ['R', 'M', 'D', 'U', 'W', 'O']  # Register, Message, Delete, etc.
            return msg_type in write_types
        except:
            return False
    
    def _replicate_operation(self, data: bytes):
        """
        Replicate an operation to all backup servers.
        
        Args:
            data: Operation data to replicate
        """
        # Add to operation log
        with self.log_lock:
            self.operation_log.append(data)
        
        # Send to all backup servers
        for replica in self.replica_addresses:
            # Skip self
            if replica == self.local_address:
                continue
                
            try:
                # Create replication message
                replication_msg = {
                    "type": "REPLICATE",
                    "term": self.current_term,
                    "server_id": self.server_id,
                    "operation": data.decode('utf-8')
                }
                
                # Send to backup
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)  # 2 second timeout
                sock.connect(replica)
                sock.sendall(json.dumps(replication_msg).encode('utf-8'))
                sock.close()
            except Exception as e:
                print(f"Error replicating to {replica}: {e}")
    
    def _replication_listener(self):
        """Listen for replication messages from other servers."""
        while self.running:
            try:
                client_sock, addr = self.replication_socket.accept()
                threading.Thread(target=self._handle_replication_connection, 
                                args=(client_sock, addr)).start()
            except Exception as e:
                if self.running:
                    print(f"Replication listener error: {e}")
    
    def _handle_replication_connection(self, client_sock: socket.socket, addr):
        """
        Handle a connection from another replica.
        
        Args:
            client_sock: Client socket
            addr: Client address
        """
        try:
            data = client_sock.recv(4096)
            if not data:
                return
                
            message = json.loads(data.decode('utf-8'))
            message_type = message.get("type", "")
            
            if message_type == "HEARTBEAT":
                self._handle_heartbeat(message)
            elif message_type == "REQUEST_VOTE":
                response = self._handle_vote_request(message)
                client_sock.sendall(json.dumps(response).encode('utf-8'))
            elif message_type == "VOTE_RESPONSE":
                self._handle_vote_response(message)
            elif message_type == "REPLICATE":
                self._handle_replication(message)
                # Send acknowledgment
                response = {"type": "REPLICATE_ACK", "server_id": self.server_id}
                client_sock.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"Error handling replication connection: {e}")
        finally:
            client_sock.close()
    
    def _handle_heartbeat(self, message):
        """
        Handle a heartbeat message from the primary.
        
        Args:
            message: Heartbeat message
        """
        sender_term = message.get("term", 0)
        sender_id = message.get("server_id", "")
        
        with self.state_lock:
            # If we receive a heartbeat from a server with a higher term,
            # update our term and recognize it as the primary
            if sender_term >= self.current_term:
                self.current_term = sender_term
                self.primary_id = sender_id
                self.role = ServerRole.BACKUP
                self.voted_for = None
                
                # Add to active replicas
                self.active_replicas.add(sender_id)
    
    def _handle_vote_request(self, message):
        """
        Handle a vote request from a candidate.
        
        Args:
            message: Vote request message
            
        Returns:
            Vote response message
        """
        candidate_term = message.get("term", 0)
        candidate_id = message.get("server_id", "")
        
        with self.vote_lock:
            # If the candidate's term is higher than ours, update our term
            if candidate_term > self.current_term:
                self.current_term = candidate_term
                self.voted_for = None
                
                # If we were the primary, step down
                if self.role == ServerRole.PRIMARY:
                    self.role = ServerRole.BACKUP
                    self.primary_id = None
            
            # Decide whether to vote for the candidate
            vote_granted = False
            if candidate_term >= self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
                self.voted_for = candidate_id
                vote_granted = True
            
            return {
                "type": "VOTE_RESPONSE",
                "term": self.current_term,
                "server_id": self.server_id,
                "vote_granted": vote_granted
            }
    
    def _handle_vote_response(self, message):
        """
        Handle a vote response from another server.
        
        Args:
            message: Vote response message
        """
        sender_term = message.get("term", 0)
        sender_id = message.get("server_id", "")
        vote_granted = message.get("vote_granted", False)
        
        with self.state_lock:
            # If we're not a candidate or the term has changed, ignore
            if self.role != ServerRole.CANDIDATE or sender_term > self.current_term:
                if sender_term > self.current_term:
                    self.current_term = sender_term
                    self.role = ServerRole.BACKUP
                    self.voted_for = None
                return
            
            # Count votes if we're still a candidate
            if vote_granted:
                self.active_replicas.add(sender_id)
                
                # If we have a majority of votes, become the primary
                if len(self.active_replicas) > len(self.replica_addresses) / 2:
                    self.role = ServerRole.PRIMARY
                    self.primary_id = self.server_id
                    print(f"Server {self.server_id} elected as PRIMARY for term {self.current_term}")
    
    def _handle_replication(self, message):
        """
        Handle a replication message from the primary server.
        
        Args:
            message: Replication message
        """
        sender_term = message.get("term", 0)
        sender_id = message.get("server_id", "")
        operation_data = message.get("operation", "")
        
        print(f"Received replication from {sender_id}, term {sender_term}")
        print(f"Operation data: {operation_data[:100]}...")  # Print first 100 chars
        
        # Only apply operations from the primary server
        if self.role == ServerRole.BACKUP and sender_id == self.primary_id and sender_term >= self.current_term:
            try:
                # Update term if necessary
                if sender_term > self.current_term:
                    self.current_term = sender_term
                
                # Apply the operation
                if operation_data:
                    # Convert operation_data from string back to bytes
                    operation_bytes = operation_data.encode('utf-8')
                    
                    # Log the operation
                    print(f"Applying operation: {operation_data[:100]}...")
                    
                    # Process the operation as if it came from a client
                    result = self.client_handler(operation_bytes, None)
                    
                    # Log the result
                    if result:
                        print(f"Successfully applied operation, result: {result[:100]}...")
                    else:
                        print("Operation applied but no result returned")
                    
                    # Add to operation log
                    with self.log_lock:
                        self.operation_log.append(operation_bytes)
                    
                    return True
                else:
                    print("Empty operation data received")
                    return False
            except Exception as e:
                print(f"Error applying operation: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print(f"Ignoring replication from {sender_id} (role={self.role}, primary={self.primary_id}, term={sender_term}/{self.current_term})")
            return False
    
    def _heartbeat_loop(self):
        """Send heartbeats if this server is the primary."""
        while self.running:
            with self.state_lock:
                if self.role == ServerRole.PRIMARY:
                    self._send_heartbeats()
            
            # Sleep for a short time
            time.sleep(0.5)  # 500ms heartbeat interval
    
    def _send_heartbeats(self):
        """Send heartbeats to all other servers."""
        heartbeat_msg = {
            "type": "HEARTBEAT",
            "term": self.current_term,
            "server_id": self.server_id
        }
        
        for replica in self.replica_addresses:
            # Skip self
            if replica == self.local_address:
                continue
                
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout
                sock.connect(replica)
                sock.sendall(json.dumps(heartbeat_msg).encode('utf-8'))
                sock.close()
            except Exception as e:
                print(f"Error sending heartbeat to {replica}: {e}")
    
    def _election_timeout_loop(self):
        """Check for election timeout and start election if needed."""
        while self.running:
            # Only start election if we're a backup and haven't received a heartbeat
            with self.state_lock:
                if self.role == ServerRole.BACKUP:
                    # Random election timeout between 1.5 and 3 seconds
                    timeout = random.uniform(1.5, 3.0)
                    time.sleep(timeout)
                    
                    # If we still haven't received a heartbeat, start an election
                    self._start_election()
                else:
                    # If we're already a primary or candidate, just sleep
                    time.sleep(1)
    
    def _start_election(self):
        """Start a leader election."""
        with self.state_lock:
            # Increment term and vote for self
            self.current_term += 1
            self.voted_for = self.server_id
            self.role = ServerRole.CANDIDATE
            self.active_replicas = {self.server_id}  # Vote for self
            
            print(f"Server {self.server_id} starting election for term {self.current_term}")
        
        # Send vote requests to all other servers
        vote_request = {
            "type": "REQUEST_VOTE",
            "term": self.current_term,
            "server_id": self.server_id
        }
        
        for replica in self.replica_addresses:
            # Skip self
            if replica == self.local_address:
                continue
                
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout
                sock.connect(replica)
                sock.sendall(json.dumps(vote_request).encode('utf-8'))
                
                # Wait for response
                response_data = sock.recv(4096)
                if response_data:
                    response = json.loads(response_data.decode('utf-8'))
                    self._handle_vote_response(response)
                
                sock.close()
            except Exception as e:
                print(f"Error requesting vote from {replica}: {e}")
    
    def _get_server_id_from_address(self, address: Tuple[str, int]) -> str:
        """
        Convert a server address to a server ID.
        
        Args:
            address: (host, port) tuple
            
        Returns:
            Server ID string
        """
        return f"{address[0]}:{address[1]}"
