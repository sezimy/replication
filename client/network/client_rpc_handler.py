from xmlrpc.client import ServerProxy
from typing import Callable
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path
from interfaces.client_communication_interface import ClientCommunicationInterface
import queue
import json

class ClientRpcHandler(ClientCommunicationInterface):
    def __init__(self):
        self.server = None
        self.running = False
        self.username = None
        self.message_queue = queue.Queue()  # Thread-safe queue

    def start_server(self, host: str, port: int) -> None:
        """Connect to the RPC server"""
        try:
            print(f"\n[RPC Client] Connecting to server at http://{host}:{port}")
            self.server = ServerProxy(f'http://{host}:{port}')
            self.running = True
            print("[RPC Client] Connected successfully")
            return True
        except Exception as e:
            print(f"[RPC Client] Connection failed: {e}")
            return False

    def stop_server(self) -> None:
        """Disconnect from the RPC server"""
        print("[RPC Client] Disconnecting...")
        self.running = False
        self.server = None
        print("[RPC Client] Disconnected")

    def send_message(self, message: bytes) -> dict:
        """Send a message through RPC and handle any responses"""
        if not self.server:
            raise ConnectionError("Not connected to server")
        try:
            # Convert bytes to string for RPC transmission
            message_str = message.decode('utf-8')
            print(f"[RPC Client] Sending message: {message_str[:100]}...")
            
            # Get response from server
            response = self.server.send_message(message_str)
            print(f"[RPC Client] Received response: {response}...")
            
            # If this is a login response with messages, queue them
            try:
                response_data = json.loads(response)
                result = response_data.get('result', {})
                return result
            except Exception as e:
                print(f"[RPC Client] Error processing messages: {e}")
            
            # Return the immediate response
            return response.encode('utf-8') if response else b''
            
        except Exception as e:
            print(f"[RPC Client] Failed to send message: {e}")
            raise

    def get_message(self, num_messages: int) -> bytes:
        """Don't need this since we get it instantly from the server"""
        pass