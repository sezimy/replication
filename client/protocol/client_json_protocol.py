import json
from datetime import datetime
from typing import Tuple, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path
from interfaces.client_serialization_interface import ClientSerializationInterface

class ClientJsonProtocol(ClientSerializationInterface):
    def __init__(self):
        super().__init__()

    def serialize_message(self, msg_type: str, payload_data: list) -> bytes:
        """Serialize a message with type and payload"""
        if msg_type == 'M':  # Chat message
            data = {
                "type": msg_type,
                "payload": {
                    "sender": payload_data[0],
                    "recipient": payload_data[1],
                    "message": payload_data[2]
                }
            }
        elif msg_type == 'D':  # Delete message
            data = {
                "type": msg_type,
                "payload": {
                    "message": payload_data[0],
                    "timestamp": payload_data[1],
                    "sender": payload_data[2],
                    "receiver": payload_data[3] if len(payload_data) > 3 else None
                }
            }
        elif msg_type == 'U':  # Delete user
            data = {
                "type": msg_type,
                "payload": {
                    "username": payload_data[0]
                }
            }
        elif msg_type == 'W':  # Update view count
            data = {
                "type": msg_type,
                "payload": {
                    "username": payload_data[0],
                    "new_count": payload_data[1]
                }
            }
        elif msg_type == 'O':  # Log off
            data = {
                "type": msg_type,
                "payload": {
                    "username": payload_data[0]
                }
            }
        else:
            data = {
                "type": msg_type,
                "payload": payload_data
            }
        
        return json.dumps(data, default=self._json_serial).encode('utf-8')

    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def serialize_user_list(self) -> bytes:
        """Serialize a request for user list"""
        data = {
            "type": "G",
            "payload": None
        }
        return json.dumps(data).encode('utf-8')

    def deserialize_message(self, payload: dict) -> Tuple[str, str, str]:
        """Deserialize a chat message"""
        return (
            payload.get("sender", ""),
            payload.get("recipient", ""),
            payload.get("message", "")
        )

    def deserialize_bulk_messages(self, payload: dict, username: str, messages_by_user: dict) -> List[Tuple[str, str]]:
        """Deserialize bulk messages"""
        messages_to_process = []
        
        print(f"Deserializing bulk messages: {type(payload)}")
        print(f"Payload content sample: {str(payload)[:200]}...")
        
        # If payload is already a dictionary, use it directly
        if isinstance(payload, dict):
            message_dict = payload
        else:
            # Try to parse as JSON if it's a string
            try:
                message_dict = json.loads(payload) if isinstance(payload, str) else payload
            except (json.JSONDecodeError, TypeError):
                print(f"Error parsing message payload: {payload}")
                return messages_to_process
        
        # Process each user's messages
        for user, messages in message_dict.items():
            if user not in messages_by_user:
                messages_by_user[user] = []
            
            print(f"Processing {len(messages)} messages for user {user}")
            
            for msg in messages:
                try:
                    # Handle timestamp which could be in various formats
                    timestamp_str = ""
                    if "timestamp" in msg:
                        if isinstance(msg["timestamp"], str):
                            # Already a string, try to format it nicely if it's ISO format
                            try:
                                dt = datetime.fromisoformat(msg["timestamp"])
                                timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # If not a valid ISO format, use as is
                                timestamp_str = msg["timestamp"]
                        else:
                            # Try to format as datetime object
                            try:
                                timestamp_str = msg["timestamp"].strftime('%Y-%m-%d %H:%M:%S')
                            except AttributeError:
                                # If not a datetime object, convert to string
                                timestamp_str = str(msg["timestamp"])
                    else:
                        # No timestamp, use current time
                        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                    # Ensure sender and receiver are properly extracted
                    sender = msg.get('sender', 'Unknown')
                    receiver = msg.get('receiver', 'Unknown')
                    message = msg.get('message', '')
                    
                    # Format the message for display
                    formatted_msg = f"[{timestamp_str}] [{sender} -> {receiver}]: {message}"
                    print(f"Formatted message: {formatted_msg}")
                    
                    # Add to the user's message list
                    messages_by_user[user].append(formatted_msg)
                    messages_to_process.append((user, formatted_msg))
                except Exception as e:
                    print(f"Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        print(f"Processed {len(messages_to_process)} total messages")
        return messages_to_process

    def deserialize_user_list(self, payload: list) -> List[str]:
        """Deserialize list of users"""
        print(f"Deserialized json user list: {payload}")
        return payload

    def deserialize_user_stats(self, payload: dict) -> Tuple[str, int]:
        """Deserialize user stats (log-off time and view count)"""
        print(f"Deserialized json user stats: {payload}")
        log_off_time = payload.get("log_off_time")
        view_count = payload.get("view_count", 5)
        
        # Handle log_off_time which could be None or a string
        if log_off_time is None:
            return ("None", view_count)  
        elif isinstance(log_off_time, str):
            # Just return the ISO format string as is - don't try to parse it
            return (log_off_time, view_count)
        else:
            # If it's a datetime object, convert to ISO format string
            try:
                return (log_off_time.isoformat(), view_count)
            except AttributeError:
                # If it's neither None, string, nor datetime, return as string
                return (str(log_off_time), view_count)

    def deserialize_success(self, payload: str) -> str:
        """Deserialize success message"""
        if isinstance(payload, dict) or isinstance(payload, list):
            return json.dumps(payload)
        return payload

    def deserialize_error(self, payload: str) -> str:
        """Deserialize error message"""
        if isinstance(payload, dict) or isinstance(payload, list):
            return json.dumps(payload)
        return payload

    def serialize_delete_message(self, message: str, timestamp: str, sender: str, receiver: str) -> bytes:
        """Serialize message deletion request"""
        data = {
            "type": "D",
            "payload": {
                "message": message,
                "timestamp": timestamp,
                "sender": sender,
                "receiver": receiver
            }
        }
        return json.dumps(data).encode('utf-8')