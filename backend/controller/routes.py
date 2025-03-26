import os
import sys
import threading
import socket
import argparse
import time
import logging
import signal
import json

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# importing interfaces
from backend.interfaces.business_logic_interface import BusinessLogicInterface
from backend.interfaces.db_interface import MongoDBInterface
from backend.interfaces.serialization_interface import SerializationInterface

# importing implementations
from backend.interactor.business_logic import BusinessLogic
from backend.database.file_operations import FileOperation

# importing protocols
from backend.protocol.json_protocol import JsonProtocol

# importing replication
from backend.replication.replication_manager import ReplicationManager

# importing socket
from backend.socket.socket_handler import SocketHandler

# Global variables
controller = None
replication_manager = None
socket_handler = None
running = False
args = None

class Controller:
    def __init__(self, business_logic: BusinessLogicInterface, json_protocol: SerializationInterface):
        self.business_logic = business_logic
        self.json_protocol = json_protocol
        self.online_users = {}  # Track online users {username: client_socket}
        self.lock = threading.Lock()  # For thread-safe operations

    def handle_incoming_message(self, data: bytes, client_socket: socket.socket=None):
        print(f"Received data: {data}")
        print(f"Client socket: {client_socket}")
        
        try:
            return replication_manager.handle_client_operation(data,client_socket)
        except Exception as e:
            print(f"Error handling incoming message: {e}")
            return self.json_protocol.serialize_error(f"Error: {str(e)}")

    
    def deserialize_message(self, data: bytes, client_socket: socket.socket=None):
        print(f"Received data: {data}")
        print(f"Client socket: {client_socket}")
        
        try:
            # For JSON, decode the entire message
            decoded_data = json.loads(data.decode('utf-8'))
            msg_type = decoded_data.get('type')
            payload = decoded_data.get('payload')
            
            if msg_type == 'R':  # Register
                username, password = self.json_protocol.deserialize_register(payload)
                
                success = self.business_logic.create_user(username, password)
                if success:
                    return self.json_protocol.serialize_success("User created successfully")
                else:
                    return self.json_protocol.serialize_error("Username already exists")
            elif msg_type == 'L':  # Login
                username, password = self.json_protocol.deserialize_login(payload)
                
                success = self.business_logic.login_user(username, password)
                if success:
                    # Track the user as online
                    if client_socket:
                        with self.lock:
                            print(f"Lock acquired, adding {username} to online_users")
                            self.online_users[username] = client_socket
                    
                    # Get user data and messages
                    user_data = self.business_logic.get_user(username)
                    messages = self.business_logic.get_messages(username)
                    
                    # Extract user stats
                    log_off_time = None
                    view_count = 5  # Default
                    
                    if user_data and len(user_data) > 0:
                        # Use the first user document (there might be multiple with same username)
                        user_doc = user_data[0]
                        log_off_time = user_doc.get('log_off_time')
                        view_count = user_doc.get('view_count', 5)
                    
                    # Just return a simple success response
                    # We'll handle user stats separately
                    return self.json_protocol.serialize_success("Login successful")
                else:
                    return self.json_protocol.serialize_error("Invalid username or password")
            elif msg_type == 'GS':  # Get User Stats
                print(f"Received GS request with payload: {payload}, type: {type(payload)}")
                
                # Handle different payload formats
                username = None
                try:
                    if isinstance(payload, list) and len(payload) > 0:
                        username = payload[0]
                        print(f"Extracted username from list: {username}")
                    elif isinstance(payload, dict):
                        username = payload.get("username")
                        print(f"Extracted username from dict: {username}")
                    else:
                        print(f"Invalid payload format for GS request: {payload}")
                        return self.json_protocol.serialize_error("Invalid payload format")
                except Exception as e:
                    print(f"Error extracting username from payload: {e}")
                    return self.json_protocol.serialize_error(f"Error extracting username: {e}")
                
                if not username:
                    print("Missing username in GS request")
                    return self.json_protocol.serialize_error("Missing username")
                
                try:
                    # Get user data
                    user_data = self.business_logic.get_user(username)
                    print(f"User data for stats: {user_data}, type: {type(user_data)}")
                    
                    # Extract user stats
                    log_off_time = None
                    view_count = 5  # Default
                    
                    # Handle different return types from get_user
                    if isinstance(user_data, list) and len(user_data) > 0:
                        # Use the first user document (there might be multiple with same username)
                        user_doc = user_data[0]
                        log_off_time = user_doc.get('log_off_time')
                        view_count = user_doc.get('view_count', 5)
                        print(f"Found stats from list: log_off_time={log_off_time}, view_count={view_count}")
                    elif isinstance(user_data, dict):
                        # User data is already a single document
                        log_off_time = user_data.get('log_off_time')
                        view_count = user_data.get('view_count', 5)
                        print(f"Found stats from dict: log_off_time={log_off_time}, view_count={view_count}")
                    else:
                        print(f"No user data found for username: {username}")
                    
                    # Return user stats
                    response = self.json_protocol.serialize_user_stats(log_off_time, view_count)
                    print(f"Sending user stats response: {response}")
                    return response
                except Exception as e:
                    import traceback
                    error_traceback = traceback.format_exc()
                    print(f"Error processing user stats: {e}")
                    print(f"Traceback: {error_traceback}")
                    return self.json_protocol.serialize_error(f"Error processing user stats: {e}")
            elif msg_type == 'M':  # Message
                sender, receiver, message = self.json_protocol.deserialize_message(payload)
                
                # Send the message
                success = self.business_logic.send_message(sender, receiver, message)
                
                # If message was sent successfully and receiver is online, notify them
                if success:
                    # Create a notification message for the receiver
                    notification = {
                        "type": "M",  # Notification
                        "payload": {
                            "sender": sender,
                            "recipient": receiver,
                            "message": message,
                        }
                    }
                    
                    # Check if receiver is online
                    print(f"Attempting to acquire lock to check if {receiver} is online")
                    print(f"Current online users: {self.online_users}")
                    with self.lock:
                        print(f"Lock acquired, checking if {receiver} is in online_users")
                        if receiver in self.online_users:
                            try:
                                # Send notification to receiver
                                receiver_socket = self.online_users[receiver]
                                print(f"Found socket for {receiver} in online_users")
                                notification_data = json.dumps(notification).encode('utf-8')
                                receiver_socket.sendall(notification_data)
                                print(f"Sent notification to {receiver}")
                            except Exception as e:
                                print(f"Error sending notification to {receiver}: {e}")
                        else:
                            print(f"Receiver {receiver} not found in online_users")
                    print(f"Lock released after checking {receiver}")
                    
                    return self.json_protocol.serialize_success("Message sent successfully")
                else:
                    return self.json_protocol.serialize_error("Message not sent")
            elif msg_type == 'GM':  # Get Messages for a specific user
                # Extract username from payload
                username = payload[0] if isinstance(payload, list) and len(payload) > 0 else None
                
                if not username:
                    return self.json_protocol.serialize_error("Invalid username")
                
                # Get all messages for this user
                messages = self.business_logic.get_messages(username)
                
                # Serialize and return the messages
                print(f"Sending {len(messages)} message threads to {username}")
                
                # Use the new serialize_messages method to format the messages properly
                response = self.json_protocol.serialize_messages(messages)
                print(f"Serialized message response: {response[:100]}...")
                return response
            elif msg_type == 'G':  # Get User List
                user_list = self.business_logic.get_all_users()
                serialized_user_list = self.json_protocol.serialize_user_list(user_list)
                print(f"Sending user list: {len(serialized_user_list)} bytes")  
                return serialized_user_list
            elif msg_type == 'D':  # Delete Message
                message, timestamp, sender, receiver = self.json_protocol.deserialize_delete_message(payload)
                    
                did_delete = self.business_logic.delete_message(message, timestamp, sender, receiver)
                if did_delete:
                    return self.json_protocol.serialize_success("Message deleted")
                else:
                    return self.json_protocol.serialize_error("Message not deleted")
                
            elif msg_type == 'U':  # Delete User
                username = self.json_protocol.deserialize_delete_user(payload)
                    
                success = self.business_logic.delete_user(username)
                if success:
                    return self.json_protocol.serialize_success("User deleted successfully")
                else:
                    return self.json_protocol.serialize_error("Failed to delete user")
                
            elif msg_type == 'W':  # Update view count
                username, new_count = self.json_protocol.deserialize_view_count_update(payload)
                    
                success = self.business_logic.update_view_count(new_count, username)
                if success:
                    return self.json_protocol.serialize_success("View count updated")
                else:
                    return self.json_protocol.serialize_error("Failed to update view count")
            elif msg_type == 'O':  # Log off
                username = self.json_protocol.deserialize_log_off(payload)
                
                success = self.business_logic.update_log_off_time(username)
                if success:
                    return self.json_protocol.serialize_success("Log off time updated")
                else:
                    return self.json_protocol.serialize_error("Failed to update log off time")
            else:
                return self.json_protocol.serialize_error("Invalid message type")
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"Error processing message: {e}")
            print(f"Traceback: {error_traceback}")
            return self.json_protocol.serialize_error(f"Error: {str(e)}")

def handle_client_request(data, client_socket, is_replication=False):
    """Handle a client request"""
    global controller, replication_manager
    
    try:
        # Log the incoming request
        print(f"handle_client_request: Received client request: {data[:100]}...")
        print(f"handle_client_request: Client socket: {client_socket}")
        
        # Check if we have a primary
        print(f"handle_client_request: Checking if we are primary")
        if not replication_manager.is_primary() and not is_replication:
            print(f"handle_client_request: We are not primary, forwarding request")
            # We're not the primary, so we need to forward the request to the primary
            primary = replication_manager.get_primary()
            if primary:
                print(f"handle_client_request: Forwarding request to primary: {primary}")
                # Create a socket to the primary
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(primary)
                s.sendall(data)
                
                # Wait for a response
                response = s.recv(4096)
                s.close()
                
                # Forward the response to the client
                if client_socket:
                    client_socket.sendall(response)
                return response
            else:
                # No primary, so we can't process the request
                print("handle_client_request: No primary available to process request")
                error_message = "No primary available to process request. Please try again later."
                error_bytes = error_message.encode('utf-8')
                if client_socket:
                    client_socket.sendall(error_bytes)
                    return error_bytes
            
        # We are the primary, so we can process the request
        if is_replication:
            print("handle_client_request: Processing request for replication")
        else:
            print("handle_client_request: We are primary, processing request")
        response = controller.deserialize_message(data, client_socket)
        print(f"handle_client_request: Got response from controller: {response[:100] if response else None}")
        
        return response
    except Exception as e:
        print(f"handle_client_request: Error handling request: {e}")
        print("handle_client_request: Full error traceback:")
        import traceback
        traceback.print_exc()
        error_message = f"Error handling request: {str(e)}"
        error_bytes = error_message.encode('utf-8')
        if client_socket:
            try:
                client_socket.sendall(error_bytes)
            except Exception as e:
                print(f"handle_client_request: Error sending error response: {e}")
        return error_bytes

def start_server():
    global controller, replication_manager, socket_handler, running, args
    parser = argparse.ArgumentParser(description='Start a chat server with replication')
    parser.add_argument('--id', type=str, required=True, help='Unique server ID')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, required=True, help='Replication port')
    parser.add_argument('--client-port', type=int, required=True, help='Client port')
    parser.add_argument('--data-dir', type=str, required=True, help='Data directory')
    parser.add_argument('--replicas', type=str, required=True, help='Comma-separated list of replicas (host:port)')
    
    args = parser.parse_args()
    
    # Create data directory if it doesn't exist
    os.makedirs(args.data_dir, exist_ok=True)
    
    # Initialize the database
    db_operations = FileOperation(args.data_dir)
    print(f"Successfully initialized file-based storage in {args.data_dir}")
    
    # Initialize the business logic
    business_logic = BusinessLogic(db_operations)
    
    # Initialize the JSON protocol
    json_protocol = JsonProtocol()
    
    # Initialize the controller
    controller = Controller(business_logic, json_protocol)
    
    # Parse the replicas string
    replicas = []
    for replica in args.replicas.split(','):
        host, port = replica.split(':')
        replicas.append((host, int(port)))
    
    # Initialize the replication manager
    local_address = (args.host, args.port)
    if local_address not in replicas:
        replicas.append(local_address)
    replication_manager = ReplicationManager(
        server_id=args.id,
        data_dir=args.data_dir,
        replica_addresses=replicas,
        local_address=local_address,
        client_handler=handle_client_request
    )
    
    # Start the replication manager
    replication_manager.start()
    
    # Initialize the socket handler for client connections
    client_port = args.client_port
    logger = logging.getLogger(__name__)
    socket_handler = SocketHandler(host='0.0.0.0', port=client_port, controller=controller, logger=logger)
    
    # Start the socket handler
    socket_handler.start_server()
    
    # Set up signal handlers
    def signal_handler(sig, frame):
        print('You pressed Ctrl+C!')
        shutdown()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep the main thread alive
    running = True
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()

def shutdown():
    global replication_manager, socket_handler
    print("\nShutting down server...")
    if replication_manager:
        replication_manager.stop()
    if socket_handler:
        socket_handler.stop_server()

if __name__ == "__main__":
    start_server()