import socket
import threading
from typing import Callable
from interfaces.communication_interface import CommunicationInterface

class SocketHandler(CommunicationInterface):
    def __init__(self):
        self.server = None
        self.running = False
        self.clients = set()
        self.lock = threading.Lock()

    def start_server(self, host: str, port: int, message_handler: Callable) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set SO_REUSEADDR option to make socket connections reusable
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        self.running = True
        print(f"Socket server running on {host}:{port}")

        while self.running:
            try:
                client_socket, client_address = self.server.accept()
                with self.lock:
                    self.clients.add(client_socket)
                self._handle_client_connection(client_socket, client_address, message_handler)
            except Exception as e:
                if self.running:  # Only log if not deliberately stopped
                    print(f"Error accepting connection: {e}")

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

    def send_message(self, client, message: bytes) -> None:
        if client in self.clients:
            try:
                client.sendall(message)
            except Exception as e:
                print(f"Error sending message: {e}")
                with self.lock:
                    self.clients.remove(client)
                    client.close()

    def _handle_client_connection(self, client_socket, client_address, message_handler):
        thread = threading.Thread(
            target=self._handle_client_messages,
            args=(client_socket, client_address, message_handler)
        )
        thread.daemon = True
        thread.start()

    def _handle_client_messages(self, client_socket, client_address, message_handler):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                response = message_handler(data, client_socket)
                if response:
                    client_socket.sendall(response)
                    
                
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            with self.lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
                client_socket.close()