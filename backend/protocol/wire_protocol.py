import struct
import json
from interfaces.serialization_interface import SerializationInterface

class WireProtocol(SerializationInterface):
    def __init__(self):
        pass

    # serialization functions

    def serialize_success(self, message: str) -> bytes:
        """
        Serializes a success message with format:
        - 1 byte for message type ('S')
        - 4 bytes for payload length
        - Variable length UTF-8 encoded message
        """
        msg_type = ord('S')  # Convert 'S' to its ASCII value
        payload = message.encode('utf-8')
        header = struct.pack('!BI', msg_type, len(payload))
        return header + payload


    def serialize_error(self, message: str) -> bytes:
        """
        Serializes an error message with format:
        - 1 byte for message type ('E')
        - 4 bytes for payload length
        - Variable length UTF-8 encoded message
        """
        msg_type = ord('E')  # Convert 'E' to its ASCII value
        payload = message.encode('utf-8')
        header = struct.pack('!BI', msg_type, len(payload))
        return header + payload

    def serialize_message(self, msg_type, payload):
        return struct.pack('!BI', ord(msg_type), len(payload)) + payload

    def serialize_all_messages(self, messages_dict: dict) -> bytes:
        """
        Serialize a dictionary of messages where each key is a user and value is a list of message objects.
        Returns a success message ('S') with the serialized messages as payload.
        """
        bulk_payload = b''
        for user, messages in messages_dict.items():
            for msg in messages:
                packed_msg = (
                    struct.pack('!H', len(msg['sender'])) + msg['sender'].encode() +
                    struct.pack('!H', len(msg['receiver'])) + msg['receiver'].encode() + 
                    struct.pack('!I', len(msg['message'])) + msg['message'].encode() + 
                    struct.pack('!I', int(msg['timestamp'].timestamp()))  # Convert to integer
                )
                bulk_payload += struct.pack('!I', len(packed_msg)) + packed_msg
        
        bulk_response = self.serialize_message('B', bulk_payload)
        print(f"Serialized messages response: {bulk_response}")
        return bulk_response

    def serialize_user_list(self, users: list) -> bytes:
        """
        Serializes a list of usernames with format:
        - 1 byte for message type ('U')
        - 4 bytes for payload length
        - For each user:
            - 2 bytes for username length
            - Variable length UTF-8 encoded username
        """
        # Prepare the payload
        payload = bytearray()
        
        # Pack each username
        for username in users:
            username_bytes = username.encode('utf-8')
            payload.extend(struct.pack('!H', len(username_bytes)))
            payload.extend(username_bytes)
            
        return self.serialize_message('U', payload)

    def serialize_user_stats(self, log_off_time, view_count) -> bytes:
        """
        Serializes user stats with format:
        - 1 byte for message type ('V')
        - 4 bytes for payload length
        - Variable length UTF-8 encoded timestamp (or 'None' if no previous log-off)
        - 4 bytes for view count
        """
        msg_type = ord('V')
        time_str = str(log_off_time) if log_off_time else "None"
        time_bytes = time_str.encode('utf-8')
        
        payload = (
            struct.pack('!H', len(time_bytes)) + time_bytes +
            struct.pack('!I', view_count)
        )
        
        header = struct.pack('!BI', msg_type, len(payload))
        print(f"Serialized user stats response: {header + payload}")
        return header + payload

    def serialize_view_count_update(self, success: bool) -> bytes:
        """Serialize view count update response"""
        if success:
            return self.serialize_success("View count updated successfully")
        else:
            return self.serialize_error("Failed to update view count")
        
    # deserialization functions

    def deserialize_register(self, payload: bytes) -> tuple:
        offset = 0
        user_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        username = payload[offset:offset+user_len].decode('utf-8')
        offset += user_len
        pass_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        password = payload[offset:offset+pass_len].decode('utf-8')
        return username, password

    def deserialize_login(self, payload: bytes) -> tuple[str, str]:
        # Login uses same format as register
        return self.deserialize_register(payload)

    def deserialize_message(self, payload: bytes) -> tuple[str, str, str]:
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

    def deserialize_delete_message(self, payload: bytes) -> tuple[str, str, str, str]:
        """Deserialize message deletion request into (message, timestamp, sender, receiver)"""
        print(f"Deserializing delete message with payload length: {len(payload)}")
        offset = 0
        
        # Get message content
        msg_len = struct.unpack_from('!H', payload, offset)[0]
        print(f"Message length: {msg_len}")
        offset += 2
        message = payload[offset:offset+msg_len].decode()
        print(f"Message: {message}")
        offset += msg_len
        print(f"Offset after message: {offset}")
        
        # Get timestamp with its length prefix
        timestamp_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        timestamp = payload[offset:offset+timestamp_len].decode()
        print(f"Timestamp: {timestamp}")
        offset += timestamp_len
        print(f"Offset after timestamp: {offset}")
        
        # Get sender
        sender_len = struct.unpack_from('!H', payload, offset)[0]
        print(f"Sender length: {sender_len}")
        offset += 2
        sender = payload[offset:offset+sender_len].decode()
        print(f"Sender: {sender}")
        offset += sender_len
        print(f"Offset after sender: {offset}")
        
        # Get receiver
        receiver_len = struct.unpack_from('!H', payload, offset)[0]
        print(f"Receiver length: {receiver_len}")
        offset += 2
        receiver = payload[offset:offset+receiver_len].decode()
        print(f"Receiver: {receiver}")
        
        return message, timestamp, sender, receiver

    def deserialize_delete_user(self, payload: bytes) -> str:
        user_len = struct.unpack_from('!H', payload, 0)[0]
        return payload[2:2+user_len].decode()

    def deserialize_view_count_update(self, payload: bytes) -> tuple[str, int]:
        offset = 0
        username_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        username = payload[offset:offset+username_len].decode()
        offset += username_len
        new_count = struct.unpack_from('!I', payload, offset)[0]
        return username, new_count
    
    def deserialize_log_off(self, payload: bytes) -> str:
        offset = 0
        username_len = struct.unpack_from('!H', payload, offset)[0]
        offset += 2
        username = payload[offset:offset+username_len].decode()
        return username