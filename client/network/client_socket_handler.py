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
        try:
            print(f"Attempting to connect to server at {host}:{port}")
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set SO_REUSEADDR option to make socket connections reusable
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Set a timeout for connection attempts
            self.server.settimeout(10)
            self.server.connect((host, port))
            # Reset timeout after connection
            self.server.settimeout(None)
            self.running = True
            print(f"Socket server running on {host}:{port}")
            return self.server
        except ConnectionRefusedError:
            print(f"Connection refused to {host}:{port}. Make sure the server is running.")
            raise
        except socket.timeout:
            print(f"Connection timeout to {host}:{port}. Server might be busy or unreachable.")
            raise
        except Exception as e:
            print(f"Error connecting to server: {e}")
            raise

    def reconnect(self) -> tuple:
        """Try to reconnect to any available server. Returns (success, new_address)"""
        try:
            
            # Try all ports again
            host = os.getenv('CHAT_APP_HOST', '0.0.0.0')
            for port in [8091, 8092, 8093]:
                try:
                    print(f"Attempting to reconnect to server at {host}:{port}")
                    self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.server.settimeout(10)
                    self.server.connect((host, port))
                    self.server.settimeout(None)
                    print(f"Successfully reconnected to {host}:{port}")
                    return True, (host, port)
                except Exception as e:
                    print(f"Failed to reconnect to {host}:{port}: {e}")
                    if self.server:
                        try:
                            self.server.close()
                        except:
                            pass
                        self.server = None
            
            print("Failed to reconnect to any server")
            return False, None
        except Exception as e:
            print(f"Error in reconnection process: {e}")
            return False, None

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

    def send_message(self, message: bytes) -> bool:
        """Send a message to the server"""
        print(f"connect to server")
        success, new_address = self.reconnect()
        if not success:
            print("Not connected to server")
            return False
        print(f"connected to server: {new_address}")
        try:
            print(f"Sending message: {message[:100]}...")
            self.server.sendall(message)
            print("Message sent successfully")
            return True
        except (socket.error, ConnectionError) as e:
            print(f"Connection error while sending: {e}")

    def get_message(self, buffer_size: int = 4096) -> bytes:
        """Get a message from the server"""
        if not self.server:
            return b''
        print(f"connected to server: {self.server}")
        try:
            # Set a short timeout to avoid blocking indefinitely
            self.server.settimeout(0.5)
            data = self.server.recv(buffer_size)
            # Reset timeout to default
            self.server.settimeout(None)
            return data
        except socket.timeout:
            # This is expected, just return empty bytes silently
            return b''
        except (socket.error, ConnectionError) as e:
            print(f"Connection error while receiving: {e}")