import json
from datetime import datetime
from interfaces.serialization_interface import SerializationInterface

class RpcProtocol(SerializationInterface):
    def __init__(self):
        pass

    # Serialization methods
    def serialize_success(self, message) -> bytes:
        """Format success response as RPC result"""
        if isinstance(message, str):
            return json.dumps({
                "jsonrpc": "2.0",
                "result": {
                    "type": "S",
                    "payload": message
                },
                "id": 1
            }).encode('utf-8')
        elif isinstance(message, dict):
            message['S'] = "Login successful"
            return json.dumps({
                "jsonrpc": "2.0",
                "result": message,
                "id": 1  # In a real RPC system, this would be dynamic
            }).encode('utf-8')
        else:
            return self.serialize_error("received non-dict or non-str response in server")

    def serialize_error(self, message: str) -> bytes:
        """Format error response as RPC error"""
        return json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "code": -32000,
                "message": message,
                "type": "E"
            },
            "id": 1
        }).encode('utf-8')

    def serialize_message(self, msg_type: str, payload: bytes) -> bytes:
        """Format message as RPC method call"""
        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
            except UnicodeDecodeError:
                payload = payload.hex()

        return json.dumps({
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": {
                "type": msg_type,
                "payload": payload
            },
            "id": 1
        }).encode('utf-8')

    def serialize_all_messages(self, messages_dict: dict) -> bytes:
        data = {
            user_key: [{
                'sender': msg['sender'],
                'receiver': msg['receiver'],
                'message': msg['message'],
                'timestamp': msg['timestamp'].isoformat()
            } for msg in msg_list]
            for user_key, msg_list in messages_dict.items()
        }
        return data
    
    def serialize_user_list(self, users: list) -> bytes:
        """Format user list as RPC response"""
        return json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "type": "U",
                "payload": users
            },
            "id": 1
        }).encode('utf-8')

    def serialize_user_stats(self, log_off_time, view_count: int) -> bytes:
        """Format user stats as RPC response"""
        data = {
            "log_off_time": log_off_time.isoformat() if log_off_time else None,
            "view_count": view_count
        }
        return data
        

    # Deserialization methods
    def deserialize_register(self, payload: dict) -> tuple[str, str]:
        """Extract registration data from RPC params"""
        if isinstance(payload, dict):
            return payload.get("username", ""), payload.get("password", "")
        return payload[0], payload[1]

    def deserialize_login(self, payload: dict) -> tuple[str, str]:
        """Extract login data from RPC params"""
        if isinstance(payload, dict):
            return payload.get("username", ""), payload.get("password", "")
        return payload[0], payload[1]

    def deserialize_message(self, payload: dict) -> tuple[str, str, str]:
        """Extract message data from RPC params"""
        if isinstance(payload, dict):
            return (
                payload.get("sender", ""),
                payload.get("recipient", ""),
                payload.get("message", "")
            )
        return payload["sender"], payload["recipient"], payload["message"]

    def deserialize_delete_message(self, payload: dict) -> tuple[str, str, str, str]:
        """Extract delete message data from RPC params"""
        if isinstance(payload, dict):
            return (
                payload.get("message", ""),
                payload.get("timestamp", ""),
                payload.get("sender", ""),
                payload.get("receiver", "")
            )
        return payload["message"], payload["timestamp"], payload["sender"], payload["receiver"]

    def deserialize_delete_user(self, payload: dict) -> str:
        """Extract delete user data from RPC params"""
        if isinstance(payload, dict):
            return payload.get("username", "")
        return payload.get("username")

    def deserialize_view_count_update(self, payload: dict) -> tuple[str, int]:
        """Extract view count update data from RPC params"""
        if isinstance(payload, dict):
            return payload.get("username", ""), payload.get("new_count", 5)
        return payload.get("username"), payload.get("new_count")
    
    def deserialize_log_off(self, payload: dict) -> str:
        """Extract log off data from RPC params"""
        if isinstance(payload, dict):
            return payload.get("username", "")
        return payload.get("username")
    
    