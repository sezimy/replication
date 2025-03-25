import struct
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path
from interfaces.client_serialization_interface import ClientSerializationInterface
from typing import Tuple, List

class ClientWireProtocol(ClientSerializationInterface):
    def __init__(self):
        super().__init__()

    def serialize_message(self, msg_type, lst) -> bytes:
        payload = b''
        if msg_type == 'M':
            payload += struct.pack('!H', len(lst[0])) + lst[0].encode()
            payload += struct.pack('!H', len(lst[1])) + lst[1].encode()
            payload += struct.pack('!I', len(lst[2])) + lst[2].encode()
        else:
            for item in lst:
                if isinstance(item, datetime): # identify the timestamp and hold it
                    print(f"timestamp: {item}")
                    payload += item.encode()
                elif isinstance(item, int):
                    payload += struct.pack('!I', item)
                else:
                    payload += struct.pack('!H', len(item)) + item.encode()

        return struct.pack('!BI', ord(msg_type), len(payload)) + payload
    
    def serialize_user_list(self) -> bytes:
        msg_type = 'G'
        payload = b''  # Empty payload for this request
        header = struct.pack('!BI', ord(msg_type), len(payload))
        return header + payload
    
    def deserialize_message(self, payload) -> Tuple[str, str, str]:
        offset = 0
        sender_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        sender = payload[offset:offset+sender_len].decode()
        offset += sender_len
        recipient_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        recipient = payload[offset:offset+recipient_len].decode()
        offset += recipient_len
        msg_len = struct.unpack_from('!I', payload, offset)[0]
        offset += 4
        msg_content = payload[offset:offset+msg_len].decode()

        return sender, recipient, msg_content
    
    def deserialize_bulk_messages(self, payload, username, messages_by_user) -> List[Tuple[str, str]]:
        try:
            messages_to_process = []
            offset = 0
            while offset < len(payload):
                # Read the length of the packed message
                msg_len = struct.unpack_from('!I', payload, offset)[0]
                offset += 4

                # Extract the packed message
                msg_data = payload[offset:offset + msg_len]
                offset += msg_len

                # Deserialize individual fields from the packed message
                sender_len = struct.unpack_from('!H', msg_data, 0)[0]
                sender = msg_data[2:2 + sender_len].decode()

                receiver_len_offset = 2 + sender_len
                receiver_len = struct.unpack_from('!H', msg_data, receiver_len_offset)[0]
                receiver = msg_data[receiver_len_offset + 2:receiver_len_offset + 2 + receiver_len].decode()

                content_offset = receiver_len_offset + 2 + receiver_len
                content_len = struct.unpack_from('!I', msg_data, content_offset)[0]
                content = msg_data[content_offset + 4:content_offset + 4 + content_len].decode()

                timestamp_offset = content_offset + 4 + content_len
                timestamp = struct.unpack_from('!I', msg_data, timestamp_offset)[0]

                # Convert timestamp to a human-readable format
                readable_timestamp = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

                # Store message by user
                other_user = sender if sender != username else receiver
                if other_user not in messages_by_user:
                    messages_by_user[other_user] = []
                
                msg_text = f"[{readable_timestamp}] [{sender} -> {receiver}]: {content}"
                messages_by_user[other_user].append(msg_text)
                messages_to_process.append((other_user, msg_text))
            
            # Update UI on main thread
            return messages_to_process
            
        except Exception as e:
            print(f"Error handling bulk messages: {e}")
    
    def deserialize_user_list(self, payload) -> List[str]:
        user_list = []  # Reset the list first
        offset = 0
        while offset < len(payload):
            username_len = struct.unpack('!H', payload[offset:offset + 2])[0]
            offset += 2
            username = payload[offset:offset + username_len].decode('utf-8')
            offset += username_len
            user_list.append(username)
        print(f"User list: {user_list}")
        return user_list
    
    def deserialize_user_stats(self, payload) -> Tuple[str, int]:
        offset = 0
        time_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        time_str = payload[offset:offset+time_len].decode()
        offset += time_len
        view_count = struct.unpack_from('!I', payload, offset)[0]
        return time_str, view_count
    
    def deserialize_success(self, payload) -> str:
        return payload.decode()
    
    def serialize_delete_message(self, message: str, timestamp: str, sender: str, receiver: str) -> bytes:
        """Serialize message deletion request"""
        payload = (
            struct.pack('!H', len(message)) + message.encode() +
            timestamp.encode() +  # Timestamp is fixed length 'YYYY-MM-DD HH:MM:SS'
            struct.pack('!H', len(sender)) + sender.encode() +
            struct.pack('!H', len(receiver)) + receiver.encode()
        )
        return struct.pack('!BI', ord('D'), len(payload)) + payload
    
