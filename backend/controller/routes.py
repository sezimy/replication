import sys
import os
import threading
import json
import socket

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
from backend.socket.socket_handler import SocketHandler

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
            # For JSON, decode the entire message
            json_data = json.loads(data.decode('utf-8'))
            msg_type = json_data['type']
            payload = json_data['payload']
            
            # Process message based on type
            if msg_type == 'R':  # Register
                username, password = self.json_protocol.deserialize_register(payload)
                success = self.business_logic.create_user(username, password)
                if success:
                    return self.json_protocol.serialize_success("User created successfully")
                else:
                    return self.json_protocol.serialize_error("Failed to create user")
                
            elif msg_type == 'L':  # Login
                username, password = self.json_protocol.deserialize_login(payload)
                maybe_success = self.business_logic.login_user(username, password)
                
                if client_socket:
                    self.online_users[username] = client_socket
                
                if maybe_success:
                    messages = self.business_logic.get_messages(username)
                    user = self.business_logic.get_user(username)
                    
                    if client_socket:
                        client_socket.sendall(self.json_protocol.serialize_success("Login successful"))
                    if messages:
                        serialized_messages = self.json_protocol.serialize_all_messages(messages)
                        if client_socket:
                            client_socket.sendall(serialized_messages)
                    
                    log_off_time = user.get('log_off_time')
                    view_count = user.get('view_count', 5)
                    return self.json_protocol.serialize_user_stats(log_off_time, view_count)
                else:
                    return self.json_protocol.serialize_error("Login failed")
                
            elif msg_type == 'M':  # Message
                sender, recipient, msg_content = self.json_protocol.deserialize_message(payload)
                    
                did_message_send = self.business_logic.send_message(sender, recipient, msg_content)
                
                with self.lock:
                    if recipient in self.online_users:
                        recipient_socket = self.online_users[recipient]
                        recipient_socket.sendall(data)

                if did_message_send:
                    return self.json_protocol.serialize_success("Message sent")
                else:
                    return self.json_protocol.serialize_error("Message not sent")
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
            print(f"Error processing message: {e}")
            return self.json_protocol.serialize_error(str(e))

def start_server():
    # Implement file-based storage operations
    file_operations = FileOperation()

    # Implement business logic
    business_logic = BusinessLogic(file_operations)

    # Use only JSON protocol
    json_protocol = JsonProtocol()
    
    # Initialize controller with JSON protocol
    controller = Controller(business_logic, json_protocol)
    
    # Initialize socket handler
    socket_handler = SocketHandler()
    
    # Start the server
    host = os.getenv('CHAT_APP_HOST', '0.0.0.0')
    port = int(os.getenv('CHAT_APP_PORT', '8081'))
    
    try:
        socket_handler.start_server(
            host, 
            port, 
            lambda data, client: controller.handle_incoming_message(data, client)
        )
        threading.Event().wait() # force main thread to block indefinitely
    except KeyboardInterrupt:
        print("\nShutting down server...")
        socket_handler.stop_server()
    except Exception as e:
        print(f"Server error: {e}")
        socket_handler.stop_server()

if __name__ == "__main__":
    start_server()