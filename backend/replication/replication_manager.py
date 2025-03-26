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
        self.last_heartbeat_time = 0  # Track last heartbeat time
        
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
        print(f"Starting replication manager for server {self.server_id}")
        self.running = True
        
        # Start replication listener
        self.replication_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.replication_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.replication_socket.bind(self.local_address)
        self.replication_socket.listen(10)
        
        print(f"Started replication listener on {self.local_address}")
        
        self.replication_listener_thread = threading.Thread(target=self._replication_listener)
        self.replication_listener_thread.daemon = True
        self.replication_listener_thread.start()
        
        # Start an election immediately
        print(f"Starting initial election for server {self.server_id}")
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
        
        print(f"Server {self.server_id} final role: {self.role}, primary_id: {self.primary_id}")
        
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
    
    def handle_client_operation(self, data: bytes) -> bytes:
        """
        Handle a client operation, possibly forwarding to the primary.
        
        Args:
            operation_type: Type of operation (read or write)
            data: Operation data
            
        Returns:
            Response bytes to send back to the client
        """
        print(f"ReplicationManager: Handling data: {data}")
        print(f"ReplicationManager: Current server state - Role: {self.role}, Primary ID: {self.primary_id}, Term: {self.current_term}")
        
        # Try multiple times in case we're in an election
        max_retries = 3
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            print(f"ReplicationManager: Attempt {attempt + 1}/{max_retries}")
            print(f"ReplicationManager: Lock status before acquiring - Is locked: {self.state_lock.locked()}")
            if self.state_lock.locked():
                print("ReplicationManager: WARNING - Lock is currently held by another thread!")
                # Let's try to identify which thread might be holding it
                import threading
                current_thread = threading.current_thread()
                print(f"ReplicationManager: Current thread: {current_thread.name}")
                print(f"ReplicationManager: All active threads:")
                for thread in threading.enumerate():
                    print(f"  - {thread.name}")
            
            with self.state_lock:
                print(f"ReplicationManager: Successfully acquired lock")
                
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
                        
                        print("ReplicationManager: About to call client_handler")
                        print(f"ReplicationManager: client_handler type: {type(self.client_handler)}")
                        response = self.client_handler(data, None)
                        print(f"ReplicationManager: client_handler returned response type: {type(response)}")
                        
                        # For write operations, replicate to backups
                        if self._is_write_operation(data):
                            print("ReplicationManager: This is a write operation, replicating to backups")
                            self._replicate_operation(data)
                        
                        print(f"ReplicationManager: Operation processed successfully, response length: {len(response) if response else 0}")
                        if response:
                            print(f"ReplicationManager: Response content: {response[:100]}")
                        return response
                    except Exception as e:
                        print(f"ReplicationManager: Error processing operation: {e}")
                        print("ReplicationManager: Full error traceback:")
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
                            if attempt < max_retries - 1:
                                print(f"Retrying after error (attempt {attempt + 1}/{max_retries})")
                                # Primary might be down, start a new election
                                self._start_election()
                                time.sleep(retry_delay)
                                continue
                            # Return error to client on last attempt
                            error_response = {"type": "E", "payload": "Primary server unavailable, trying to elect new primary"}
                            return json.dumps([error_response]).encode('utf-8')
            
            # If we don't know who the primary is, wait briefly and retry
            if attempt < max_retries - 1:
                print(f"No primary available, waiting and retrying (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
        
        # If we get here, we've exhausted all retries
        print("ReplicationManager: No primary server available after all retries")
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
            print(f"ReplicationManager: _is_write_operation: msg_type: {msg_type}")
            
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
                self._remove_dead_primary()
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
        
        # Don't process our own heartbeats
        if sender_id == self.server_id:
            print(f"Ignoring heartbeat from self ({self.server_id})")
            return
            
        print(f"Handling heartbeat from {sender_id}, term {sender_term}")
        print(f"Current state before heartbeat - Role: {self.role}, Term: {self.current_term}, Primary: {self.primary_id}")
        
        with self.state_lock:
            # Update last heartbeat time
            self.last_heartbeat_time = time.time()
            
            # Only step down if we receive a higher term
            if sender_term > self.current_term:
                print(f"Received higher term {sender_term} > {self.current_term}, stepping down")
                self.current_term = sender_term
                self.primary_id = sender_id
                self.role = ServerRole.BACKUP
                self.voted_for = None
                self.active_replicas.add(sender_id)
            elif sender_term == self.current_term:
                # If we're not PRIMARY, update our primary_id
                if self.role != ServerRole.PRIMARY:
                    print(f"Updating primary to {sender_id} for current term")
                    self.primary_id = sender_id
                else:
                    print(f"Ignoring heartbeat - we are PRIMARY for term {self.current_term}")
            else:
                print(f"Ignoring heartbeat with lower term {sender_term} < {self.current_term}")
        
        print(f"State after heartbeat - Role: {self.role}, Term: {self.current_term}, Primary: {self.primary_id}")
    
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
        
        print(f"Handling vote request from {candidate_id} for term {candidate_term}")
        
        with self.vote_lock:
            # If the candidate's term is higher than ours, update our term
            if candidate_term > self.current_term:
                print(f"Updating term from {self.current_term} to {candidate_term}")
                self.current_term = candidate_term
                self.voted_for = None
                
                # If we were the primary, step down
                if self.role == ServerRole.PRIMARY:
                    print(f"Stepping down from PRIMARY to BACKUP")
                    self.role = ServerRole.BACKUP
                    self.primary_id = None
            
            # Decide whether to vote for the candidate
            vote_granted = False
            if candidate_term >= self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
                print(f"Voting for {candidate_id}")
                self.voted_for = candidate_id
                vote_granted = True
            else:
                print(f"Not voting for {candidate_id} (term={candidate_term}, current_term={self.current_term}, voted_for={self.voted_for})")
            
            response = {
                "type": "VOTE_RESPONSE",
                "term": self.current_term,
                "server_id": self.server_id,
                "vote_granted": vote_granted
            }
            print(f"Sending vote response: {response}")
            return response
    
    def _handle_vote_response(self, message):
        """
        Handle a vote response from another server.
        
        Args:
            message: Vote response message
        """
        sender_term = message.get("term", 0)
        sender_id = message.get("server_id", "")
        vote_granted = message.get("vote_granted", False)
        
        print(f"Handling vote response from {sender_id}: term={sender_term}, vote_granted={vote_granted}")
        
        with self.state_lock:
            # If we're not a candidate or the term has changed, ignore
            if self.role != ServerRole.CANDIDATE or sender_term > self.current_term:
                if sender_term > self.current_term:
                    print(f"Updating term from {self.current_term} to {sender_term} due to higher term in vote response")
                    self.current_term = sender_term
                    self.role = ServerRole.BACKUP
                    self.voted_for = None
                return
            
            # Count votes if we're still a candidate
            if vote_granted:
                print(f"Received vote from {sender_id}")
                self.active_replicas.add(sender_id)
                
                # If we have a majority of votes, become the primary
                if len(self.active_replicas) > len(self.replica_addresses) / 2:
                    print(f"Received majority of votes ({len(self.active_replicas)}/{len(self.replica_addresses)}), becoming PRIMARY")
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
                    result = self.client_handler(operation_bytes, None, is_replication=True)
                    
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
            should_send_heartbeat = False
            heartbeat_msg = None
            
            # Check if we should send heartbeat under lock
            with self.state_lock:
                if self.role == ServerRole.PRIMARY:
                    should_send_heartbeat = True
                    heartbeat_msg = {
                        "type": "HEARTBEAT",
                        "term": self.current_term,
                        "server_id": self.server_id
                    }
            
            # Send heartbeats outside the lock if needed
            if should_send_heartbeat and heartbeat_msg:
                self._send_heartbeats(heartbeat_msg)
            
            # Sleep for a short time
            time.sleep(0.5)  # 500ms heartbeat interval
    
    def _send_heartbeats(self, heartbeat_msg):
        """Send heartbeats to all other servers."""
        print(f"Sending heartbeats as PRIMARY for term {heartbeat_msg['term']}")
        
        for replica in self.replica_addresses:
            # Skip self
            if replica == self.local_address:
                print(f"Skipping heartbeat to self ({self.local_address})")
                continue
                
            try:
                print(f"Sending heartbeat to {replica}")
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
            # Random election timeout between 1.5 and 3 seconds
            timeout = random.uniform(1.5, 3.0)
            time.sleep(timeout)
            
            should_start_election = False
            with self.state_lock:
                # Only start election if we're a backup and haven't received a heartbeat
                if self.role == ServerRole.BACKUP:
                    print(f"Server {self.server_id} considering election (current term: {self.current_term})")
                    print(f"Current replica_addresses: {self.replica_addresses}")
                    print(f"Current primary_id: {self.primary_id}")
                    
                    # Check if we've received a heartbeat recently (within random timeout)
                    current_time = time.time()
                    heartbeat_timeout = random.uniform(1.5, 3.0)  # Random timeout between 1.5 and 3 seconds
                    if current_time - self.last_heartbeat_time > heartbeat_timeout:
                        print(f"No heartbeat received for {current_time - self.last_heartbeat_time:.1f} seconds (timeout: {heartbeat_timeout:.1f}s), clearing primary")
                        self._remove_dead_primary()
                        self.primary_id = None
                        should_start_election = True
                    elif self.primary_id is None:
                        print("No primary known, will start election")
                        should_start_election = True
                    else:
                        print(f"Have primary {self.primary_id}, skipping election")
                else:
                    print(f"Not starting election - current role is {self.role}")
            
            # Start election outside the lock if needed
            if should_start_election:
                print(f"Starting election outside lock")
                self._start_election()
            else:
                time.sleep(1)  # Sleep outside the lock
    
    def _start_election(self):
        """Start a leader election."""
        with self.state_lock:
            # Don't start election if we're already PRIMARY
            if self.role == ServerRole.PRIMARY:
                print(f"Skipping election start - already PRIMARY")
                return
                
            # Don't start election if we already know about a valid primary
            if self.primary_id is not None:
                print(f"Skipping election start - already have primary {self.primary_id}")
                return
                
            print(f"Starting election process for server {self.server_id}")
            
            # Increment term and vote for self
            self.current_term += 1
            self.voted_for = self.server_id
            self.role = ServerRole.CANDIDATE
            self.active_replicas = {self.server_id}  # Vote for self
            self.primary_id = None  # Clear primary_id since we're starting an election
            
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
                print(f"Requesting vote from {replica}")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout
                sock.connect(replica)
                sock.sendall(json.dumps(vote_request).encode('utf-8'))
                
                # Wait for response
                response_data = sock.recv(4096)
                if response_data:
                    response = json.loads(response_data.decode('utf-8'))
                    print(f"Received vote response from {replica}: {response}")
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
    
    def is_primary(self) -> bool:
        """Check if this server is the primary."""
        is_primary = self.role == ServerRole.PRIMARY
        print(f"ReplicationManager.is_primary: Checking if primary - Role: {self.role}, Result: {is_primary}")
        return is_primary
            
    def get_primary(self) -> Optional[Tuple[str, int]]:
        """Get the address of the primary server."""
        if self.primary_id:
            print(f"ReplicationManager.get_primary: Primary ID is {self.primary_id}")
            # Find the primary's address
            for replica in self.replica_addresses:
                if self._get_server_id_from_address(replica) == self.primary_id:
                    print(f"ReplicationManager.get_primary: Found primary address {replica}")
                    return replica
        print("ReplicationManager.get_primary: No primary found")
        return None
    
    def _remove_dead_primary(self):
        """Remove the dead primary from replica_addresses if we know who it was."""
        # Remove dead primary from replica_addresses if we know who it was
        if self.primary_id:
            print(f"Attempting to remove dead primary {self.primary_id} from replica_addresses")
            dead_primary = None
            # Extract replica number from primary_id (e.g., "replica1" -> "1")
            primary_number = self.primary_id.replace("replica", "")
            print(f"Looking for replica number: {primary_number}")
            
            for replica in self.replica_addresses:
                # Extract replica number from address (e.g., "localhost:8081" -> "1")
                replica_number = str(replica[1] - 8080)  # Convert port to replica number
                print(f"Checking replica {replica} -> number: {replica_number}")
                if replica_number == primary_number:
                    dead_primary = replica
                    print(f"Found dead primary at {replica}")
                    break
            if dead_primary:
                print(f"Removing dead primary {dead_primary} from replica_addresses")
                self.replica_addresses.remove(dead_primary)
                print(f"Updated replica_addresses: {self.replica_addresses}")
            else:
                print(f"Could not find dead primary {self.primary_id} in replica_addresses")
        else:
            print(f"No primary_id so no dead primary to remove")
    
