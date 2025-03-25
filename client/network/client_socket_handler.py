import socket
import threading
from typing import Callable
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path
from interfaces.client_communication_interface import ClientCommunicationInterface

class ClientSocketHandler(ClientCommunicationInterface):
        
    def __init__(self):
        self.server = None
        self.running = False
        self.clients = set()
        self.lock = threading.Lock()

    def start_server(self, host: str, port: int) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set SO_REUSEADDR option to make socket connections reusable
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.connect((host, port))
        self.running = True
        print(f"Socket server running on {host}:{port}")
        return self.server
    
    def stop_server(self) -> None:
        self.running = False
        if self.server:
            self.server.close()
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()

    def send_message(self, message: bytes) -> None:
        self.server.sendall(message)

    def get_message(self, num_messages: int) -> bytes:
        data = self.server.recv(num_messages)
        return data