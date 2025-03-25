from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any

class SerializationInterface(ABC):
    # Serialization methods
    @abstractmethod
    def serialize_success(self, message: any) -> bytes:
        # dict for rpc
        # string for json and wire
        pass
    
    @abstractmethod
    def serialize_error(self, message: str) -> bytes:
        pass
    
    @abstractmethod
    def serialize_message(self, msg_type: str, payload: bytes) -> bytes:
        pass
    
    @abstractmethod
    def serialize_all_messages(self, messages_dict: Dict[str, List[Dict[str, Any]]]) -> bytes:
        pass
    
    @abstractmethod
    def serialize_user_list(self, users: List[str]) -> bytes:
        pass
    
    @abstractmethod
    def serialize_user_stats(self, log_off_time: Any, view_count: int) -> bytes:
        pass
    
    # Deserialization methods
    @abstractmethod
    def deserialize_register(self, payload: bytes) -> Tuple[str, str]:
        """Deserialize registration payload into (username, password)"""
        pass
    
    @abstractmethod
    def deserialize_login(self, payload: bytes) -> Tuple[str, str]:
        """Deserialize login payload into (username, password)"""
        pass
    
    @abstractmethod
    def deserialize_message(self, payload: bytes) -> Tuple[str, str, str]:
        """Deserialize message payload into (sender, recipient, message)"""
        pass
    
    @abstractmethod
    def deserialize_delete_message(self, payload: bytes) -> Tuple[str, str, str, str]:
        """Deserialize delete message payload into (message, timestamp, sender, receiver)"""
        pass
    
    @abstractmethod
    def deserialize_delete_user(self, payload: bytes) -> str:
        """Deserialize delete user payload into username"""
        pass
    
    @abstractmethod
    def deserialize_view_count_update(self, payload: bytes) -> Tuple[str, int]:
        """Deserialize view count update payload into (username, new_count)"""
        pass
