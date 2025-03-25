from abc import ABC, abstractmethod
from typing import Callable

class CommunicationInterface(ABC):
    @abstractmethod
    def start_server(self, host: str, port: int) -> None:
        """Start the server and listen for connections"""
        pass
    
    @abstractmethod
    def stop_server(self) -> None:
        """Stop the server and clean up resources"""
        pass
    
    @abstractmethod
    def send_message(self, client, message: bytes) -> None:
        """Send a message to a client"""
        pass 