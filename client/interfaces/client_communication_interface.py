from abc import ABC, abstractmethod
from typing import Callable

class ClientCommunicationInterface(ABC):
    @abstractmethod
    def start_server(self, host: str, port: int) -> None:
        """Connect to the server"""
        pass
    
    @abstractmethod
    def stop_server(self) -> None:
        """Disconnect from the server"""
        pass
    
    @abstractmethod
    def send_message(self, message: bytes) -> any:
        """Send a message and get response"""
        pass
    
    @abstractmethod
    def get_message(self, num_messages: int):
        """Get a list of messages"""
        pass