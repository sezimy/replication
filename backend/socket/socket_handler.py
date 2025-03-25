import socket
import threading
import logging
import time
from typing import Callable
from interfaces.communication_interface import CommunicationInterface

class SocketHandler(CommunicationInterface):
    """Socket handler for the server"""
    def __init__(self, host: str, port: int, controller, logger=None):
        self.host = host
        self.port = port
        self.controller = controller
        self.socket = None
        self.running = False
        self.clients = []
        self.client_threads = []
        self.logger = logger or logging.getLogger(__name__)
        self.lock = threading.Lock()
        self.message_handler = None

    def start_server(self, message_handler=None):
        """Start the socket server"""
        self.message_handler = message_handler or self.controller.handle_incoming_message
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            self.logger.info(f"Socket server running on {self.host}:{self.port}")
            print(f"Socket server running on {self.host}:{self.port}")
            
            # Start accepting clients
            accept_thread = threading.Thread(target=self.accept_clients)
            accept_thread.daemon = True
            accept_thread.start()
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting socket server: {e}")
            print(f"Error starting socket server: {e}")
            import traceback
            traceback.print_exc()
            return False

    def accept_clients(self):
        """Accept client connections"""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                self.logger.info(f"New client connected: {address}")
                print(f"New client connected: {address}")
                
                # Start a new thread to handle the client
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
                
                with self.lock:
                    self.clients.append(client_socket)
                    self.client_threads.append(client_thread)
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    self.logger.error(f"Error accepting client: {e}")
                    print(f"Error accepting client: {e}")
                    import traceback
                    traceback.print_exc()
                time.sleep(0.1)  # Prevent CPU spinning

    def handle_client(self, client_socket, address):
        """Handle client connection"""
        try:
            while self.running:
                try:
                    # Set a timeout to prevent blocking indefinitely
                    client_socket.settimeout(0.5)
                    
                    # Receive data from client
                    data = client_socket.recv(4096)
                    if not data:
                        self.logger.info(f"Client disconnected: {address}")
                        print(f"Client disconnected: {address}")
                        break
                    
                    self.logger.info(f"Received data from {address}: {data[:100]}")
                    print(f"Received data from {address}: {data[:100]}")
                    
                    # Process the data
                    response = self.message_handler(data, client_socket)
                    
                    # If there's a response, send it back to the client
                    if response:
                        self.logger.info(f"Sending response to {address}: {response[:100]}")
                        print(f"Sending response to {address}: {response[:100]}")
                        client_socket.sendall(response)
                
                except socket.timeout:
                    # This is expected, just continue the loop
                    continue
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error handling client {address}: {e}")
                        print(f"Error handling client {address}: {e}")
                        import traceback
                        traceback.print_exc()
                    break
        finally:
            # Clean up
            try:
                client_socket.close()
                with self.lock:
                    if client_socket in self.clients:
                        self.clients.remove(client_socket)
            except Exception as e:
                self.logger.error(f"Error closing client socket: {e}")
                print(f"Error closing client socket: {e}")

    def stop_server(self):
        """Stop the socket server"""
        self.running = False
        
        # Close all client connections
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
        
        # Close the server socket
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.logger.error(f"Error closing server socket: {e}")
                print(f"Error closing server socket: {e}")
        
        self.logger.info("Socket server stopped")
        print("Socket server stopped")

    def broadcast(self, message, exclude=None):
        """Broadcast a message to all connected clients"""
        with self.lock:
            for client in self.clients:
                if exclude and client == exclude:
                    continue
                try:
                    client.sendall(message)
                except Exception as e:
                    self.logger.error(f"Error broadcasting message: {e}")
                    print(f"Error broadcasting message: {e}")
                    # Remove the client if we can't send to it
                    try:
                        client.close()
                        self.clients.remove(client)
                    except Exception:
                        pass

    def send_message(self, client, message: bytes) -> None:
        if client in self.clients:
            try:
                client.sendall(message)
            except Exception as e:
                self.logger.error(f"Error sending message: {e}")
                print(f"Error sending message: {e}")
                with self.lock:
                    self.clients.remove(client)
                    client.close()