from abc import ABC, abstractmethod
from typing import Tuple, List
import struct
class ClientSerializationInterface:
    def __init__(self):
        pass

    @abstractmethod
    def serialize_message(self, msg_type, payload, lst) -> bytes:
        pass

    @abstractmethod
    def serialize_user_list(self) -> bytes:
        pass
    
    @abstractmethod
    def deserialize_message(self, payload) -> Tuple[str, str, str]:
        pass
    
    @abstractmethod
    def deserialize_bulk_messages(self, payload, username, messages_by_user) -> List[Tuple[str, str]]:
        pass

    @abstractmethod
    def deserialize_user_list(self, users) -> List[str]:
        pass
    
    @abstractmethod
    def deserialize_user_stats(self, payload) -> Tuple[str, int]:
        pass
    
    @abstractmethod
    def deserialize_success(self, payload) -> str:
        pass

    
