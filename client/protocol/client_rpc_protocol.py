import json
from datetime import datetime
from typing import Tuple, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path
from interfaces.client_serialization_interface import ClientSerializationInterface

class ClientRpcProtocol(ClientSerializationInterface):
    def __init__(self):
        super().__init__()

    def serialize_message(self, msg_type: str, lst: list) -> bytes:
        """Format message as RPC method call"""
        if msg_type == 'M':  # Chat message
            params = {
                "type": msg_type,
                "sender": lst[0],
                "recipient": lst[1],
                "message": lst[2]
            }
        elif msg_type == 'D':  # Delete message
            params = {
                "type": msg_type,
                "message": lst[0],
                "timestamp": lst[1],
                "sender": lst[2],
                "receiver": lst[3]
            }
        elif msg_type == 'U':  # Delete user
            params = {
                "type": msg_type,
                "username": lst[0]
            }
        elif msg_type == 'W':  # Update view count
            params = {
                "type": msg_type,
                "username": lst[0],
                "new_count": lst[1]
            }
        elif msg_type == 'O':  # Log off
            params = {
                "type": msg_type,
                "username": lst[0]
            }
        else:  # Login/Register/etc
            params = {
                "type": msg_type,
                "username": lst[0],
                "password": lst[1] if len(lst) > 1 else None
            }

        return json.dumps({
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": params,
            "id": 1
        }).encode('utf-8')

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
        
        for user, messages in payload.items():
            if user not in messages_by_user:
                messages_by_user[user] = []
            
            for msg in messages:
                timestamp = datetime.fromisoformat(msg["timestamp"])
                formatted_msg = f"[{timestamp}] [{msg['sender']} -> {msg['receiver']}]: {msg['message']}"
                messages_by_user[user].append(formatted_msg)
                messages_to_process.append((user, formatted_msg))
        
        return messages_to_process

    def deserialize_user_list(self, payload: dict) -> List[str]:
        """Deserialize list of users"""
        return payload

    def deserialize_user_stats(self, payload: dict) -> Tuple[str, int]:
        """Deserialize user stats (log-off time and view count)"""
        return (
            payload.get("log_off_time"),
            payload.get("view_count", 5)
        )

    def deserialize_success(self, payload: str) -> str:
        """Deserialize success message"""
        return payload if isinstance(payload, str) else str(payload)

    def serialize_user_list(self) -> bytes:
        """Serialize a request for user list"""
        return json.dumps({
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": {"type": "G"},
            "id": 1
        }).encode('utf-8')
