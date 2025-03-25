from xmlrpc.server import SimpleXMLRPCServer
import threading
from typing import Callable
from backend.interfaces.communication_interface import CommunicationInterface
from collections import defaultdict
import queue
import json
import time
import socket
import sys

class RpcHandler(CommunicationInterface):
    def __init__(self):
        self.server = None
        self.running = False
        self.message_handler = None
        self.message_queues = defaultdict(queue.Queue)
        self.lock = threading.Lock()
        self.server_thread = None

    def start_server(self, host: str, port: int, message_handler: Callable) -> None:
        print(f"\n[RPC] Starting RPC server...")
        try:
            # Configure server with timeout
            self.server = SimpleXMLRPCServer(
                (host, port), 
                allow_none=True, 
                logRequests=True,
                bind_and_activate=False  # Don't bind immediately
            )
            
            # Set socket options
            self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Now bind and activate
            try:
                self.server.server_bind()
                self.server.server_activate()
            except Exception as e:
                print(f"[RPC] Failed to bind/activate server: {e}")
                self.stop_server()
                return

            self.message_handler = message_handler
            self.running = True
            
            # Register RPC methods
            self.server.register_function(self.send_message, "send_message")
            self.server.register_function(self.get_pending_messages, "get_pending_messages")
            self.server.register_function(self.keep_alive, "keep_alive")
            
            print(f"[RPC] Server running on {host}:{port}")
            print(f"[RPC] Registered methods: send_message, get_pending_messages, keep_alive")
            
            # Start server thread
            self.server_thread = threading.Thread(target=self._serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            print(f"[RPC] Server thread started")

            # Start watchdog thread
            watchdog_thread = threading.Thread(target=self._watchdog)
            watchdog_thread.daemon = True
            watchdog_thread.start()
            print(f"[RPC] Watchdog thread started")

        except Exception as e:
            print(f"[RPC] Failed to start server: {e}")
            self.stop_server()
            raise

    def _serve_forever(self):
        """Wrapper around serve_forever with error handling"""
        try:
            print("[RPC] Server loop starting...")
            while self.running:
                try:
                    self.server.handle_request()
                except Exception as e:
                    print(f"[RPC] Error handling request: {e}")
                    if not self.running:
                        break
                    time.sleep(0.1)  # Prevent tight loop on errors
        except Exception as e:
            print(f"[RPC] Server error: {e}")
        finally:
            print("[RPC] Server loop ended")

    def _watchdog(self):
        """Watchdog thread to monitor server health"""
        print("[RPC] is the server running?", self.running)
        while self.running:
            try:
                if not self.server_thread.is_alive():
                    print("[RPC] Server thread died, attempting restart...")
                    self.server_thread = threading.Thread(target=self._serve_forever)
                    self.server_thread.daemon = True
                    self.server_thread.start()
            except Exception as e:
                print(f"[RPC] Watchdog error: {e}")
            time.sleep(5)  # Check every 5 seconds

    def keep_alive(self) -> bool:
        """Simple method for clients to check if server is alive"""
        return True

    def stop_server(self) -> None:
        print("[RPC] Stopping server...")
        self.running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as e:
                print(f"[RPC] Error stopping server: {e}")
        print("[RPC] Server stopped")

    def send_message(self, message_str: str) -> str:
        """Handle incoming RPC messages"""
        print(f"\n[RPC] Received message: {message_str[:100]}...")  # Truncate long messages
        
        if not self.running:
            print("[RPC] Server not running")
            return ""
            
        if not self.message_handler:
            print("[RPC] No message handler registered")
            return ""

        try:
            # Convert string to bytes for consistency with interface
            message_bytes = message_str.encode('utf-8')
            print(f"[RPC] Processing message...")
            response = self.message_handler(message_bytes, None)
            response_str = response.decode('utf-8') if response else ""
            print(f"[RPC] Sending response: {response_str[:100]}...")  # Truncate long responses
            return response_str
        except Exception as e:
            print(f"[RPC] Error handling RPC message: {e}")
            return ""

    def get_pending_messages(self, username: str) -> list:
        """Retrieve pending messages for a client"""
        if not self.running:
            print("[RPC] Server not running")
            return []

        try:
            messages = []
            with self.lock:
                queue = self.message_queues.get(username, queue.Queue())
                while not queue.empty():
                    messages.append(queue.get())
            
            if messages:
                print(f"[RPC] Retrieved {len(messages)} pending messages for {username}")
            return messages
        except Exception as e:
            print(f"[RPC] Error retrieving messages: {e}")
            return [] 