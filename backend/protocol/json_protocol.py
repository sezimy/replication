import json
from datetime import datetime
from interfaces.serialization_interface import SerializationInterface

class JsonProtocol(SerializationInterface):
    def __init__(self):
        pass

    # Serialization methods
    def serialize_success(self, message: str) -> bytes:
        data = {
            "type": "S",
            "payload": message
        }
        return json.dumps(data).encode('utf-8')

    def serialize_error(self, message: str) -> bytes:
        data = {
            "type": "E",
            "payload": message
        }
        return json.dumps(data).encode('utf-8')

    def serialize_message(self, msg_type: str, payload: bytes) -> bytes:
        # Convert bytes payload to string if needed
        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
            except UnicodeDecodeError:
                payload = payload.hex()

        data = {
            "type": msg_type,
            "payload": payload
        }
        return json.dumps(data).encode('utf-8')

    def serialize_all_messages(self, messages_dict: dict) -> bytes:
        formatted_messages = {}
        for user, messages in messages_dict.items():
            formatted_messages[user] = []
            for msg in messages:
                formatted_msg = {
                    "sender": msg["sender"],
                    "receiver": msg["receiver"],
                    "message": msg["message"],
                    "timestamp": msg["timestamp"] if isinstance(msg["timestamp"], str) else msg["timestamp"].isoformat()
                }
                formatted_messages[user].append(formatted_msg)

        data = {
            "type": "B",
            "payload": formatted_messages
        }
        return json.dumps(data).encode('utf-8')

    def serialize_messages(self, messages_dict: dict) -> bytes:
        """
        Serialize a dictionary of messages for a specific user.
        
        Args:
            messages_dict: Dictionary of messages by user
            
        Returns:
            Serialized message data
        """
        # Format the messages for JSON serialization
        formatted_messages = {}
        for user, messages in messages_dict.items():
            formatted_messages[user] = []
            for msg in messages:
                # Ensure timestamp is properly formatted
                timestamp = msg["timestamp"]
                if not isinstance(timestamp, str):
                    timestamp = timestamp.isoformat()
                
                formatted_msg = {
                    "sender": msg["sender"],
                    "receiver": msg["receiver"],
                    "message": msg["message"],
                    "timestamp": timestamp,
                    "_id": msg.get("_id", "")
                }
                formatted_messages[user].append(formatted_msg)
        
        # Create the response
        data = {
            "type": "BM",  # Bulk Messages
            "payload": formatted_messages
        }
        
        # Serialize to JSON and encode as bytes
        return json.dumps(data).encode('utf-8')

    def serialize_user_list(self, users: list) -> bytes:
        data = {
            "type": "U",
            "payload": users
        }
        return json.dumps(data).encode('utf-8')

    def serialize_user_stats(self, log_off_time, view_count: int) -> bytes:
        try:
            # Add debug print to see what values we're getting
            print(f"Serializing user stats with log_off_time: {log_off_time}, view_count: {view_count}")
            
            # Ensure view_count is an integer
            if view_count is None:
                view_count = 0
            else:
                try:
                    view_count = int(view_count)
                except (ValueError, TypeError):
                    view_count = 0
            
            # Handle log_off_time properly
            if log_off_time is None:
                log_off_time_str = None
            elif isinstance(log_off_time, str):
                log_off_time_str = log_off_time
            else:
                try:
                    log_off_time_str = log_off_time.isoformat()
                except Exception as e:
                    print(f"Error formatting log_off_time: {e}")
                    log_off_time_str = None
            
            data = {
                "type": "V",
                "payload": {
                    "log_off_time": log_off_time_str,
                    "view_count": view_count
                    }
                }
            print(f"Serialized json user stats: {data}")
            return json.dumps(data).encode('utf-8')
        except Exception as e:
            print(f"Error serializing user stats: {e}")
            # Return a valid response even if there's an error
            fallback_data = {
                "type": "V",
                "payload": {
                    "log_off_time": None,
                    "view_count": 0
                    }
                }
            return json.dumps(fallback_data).encode('utf-8')

    # Deserialization methods
    def deserialize_register(self, payload: list) -> tuple[str, str]:
        return payload[0], payload[1]

    def deserialize_login(self, payload: list) -> tuple[str, str]:
        return payload[0], payload[1]

    def deserialize_message(self, payload: list) -> tuple[str, str, str]:
        return payload.get("sender"), payload.get("recipient"), payload.get("message")

    def deserialize_delete_message(self, payload: list) -> tuple[str, str, str, str]:
        return payload.get("message"), payload.get("timestamp"), payload.get("sender"), payload.get("receiver")

    def deserialize_delete_user(self, payload: list) -> str:
        return payload.get("username")

    def deserialize_view_count_update(self, payload: list) -> tuple[str, int]:
        print(f"Deserialized json view count update: {payload}")
        return payload.get("username"), payload.get("new_count")
    
    def deserialize_log_off(self, payload) -> str:
        """Deserialize log-off message to extract username
        
        Args:
            payload: Could be a list [username] or a dict {"username": username}
            
        Returns:
            The username as a string
        """
        if isinstance(payload, dict):
            return payload.get("username")
        elif isinstance(payload, list) and len(payload) > 0:
            return payload[0]
        else:
            print(f"Invalid log-off payload format: {payload}")
            return None