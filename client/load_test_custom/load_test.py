from locust import User, task, between, events
import socket
import struct
import time
from client_wire_protocol import ClientWireProtocol
import random

class ChatUser(User):
    wait_time = between(2, 5)  # Increased wait time between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_socket = None
        self.username = f"test_user_{random.randint(1, 1000)}"
        self.protocol = ClientWireProtocol()
        self.connected = False
        
    def on_start(self):
        """Initialize connection when user starts"""
        try:
            start_time = time.time()
            self.connect()
            if self.connected:
                success = self._do_login()
                total_time = int((time.time() - start_time) * 1000)
                if success:
                    events.request.fire(
                        request_type="LOGIN",
                        name="login",
                        response_time=total_time,
                        response_length=0,
                        exception=None,
                    )
                else:
                    events.request.fire(
                        request_type="LOGIN",
                        name="login",
                        response_time=total_time,
                        response_length=0,
                        exception=Exception("Login failed"),
                    )
        except Exception as e:
            events.request.fire(
                request_type="LOGIN",
                name="login",
                response_time=0,
                response_length=0,
                exception=e,
            )
            
    def connect(self):
        """Establish connection with retry logic"""
        retry_count = 3
        while retry_count > 0 and not self.connected:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5)  # 5 second timeout
                self.client_socket.connect(('localhost', 8081))
                self.connected = True
                return True
            except socket.error as e:
                print(f"Connection attempt failed: {e}, retries left: {retry_count-1}")
                retry_count -= 1
                if self.client_socket:
                    self.client_socket.close()
                time.sleep(1)
        return False
            
    def on_stop(self):
        """Clean up when user stops"""
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            
    def _do_login(self):
        """Perform login operation"""
        try:
            data = self.protocol.serialize_message('L', [self.username, "password123"])
            self.client_socket.sendall(data)
            
            header = self.client_socket.recv(4)
            if not header:
                self.connected = False
                return False
                
            msg_len = struct.unpack('!I', header)[0]
            response = self.client_socket.recv(msg_len)
            return True
        except Exception as e:
            print(f"Login error: {e}")
            self.connected = False
            return False
        
    @task(3)
    def send_message(self):
        """Send a message to random user"""
        if not self.connected:
            if not self.connect():
                return
                
        try:
            start_time = time.time()
            receiver = f"test_user_{random.randint(1, 1000)}"
            message = f"Test message {time.time()}"
            data = self.protocol.serialize_message('M', [self.username, receiver, message])
            self.client_socket.sendall(data)
            
            header = self.client_socket.recv(4)
            if not header:
                self.connected = False
                raise Exception("No response received")
                
            msg_len = struct.unpack('!I', header)[0]
            response = self.client_socket.recv(msg_len)
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="SEND",
                name="send_message",
                response_time=total_time,
                response_length=len(data),
                exception=None,
            )
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="SEND",
                name="send_message",
                response_time=total_time,
                response_length=0,
                exception=e,
            )
            self.connected = False
            
    @task(1)
    def request_user_list(self):
        """Request list of users"""
        if not self.connected:
            if not self.connect():
                return
                
        try:
            start_time = time.time()
            data = self.protocol.serialize_message('G', [])
            self.client_socket.sendall(data)
            
            header = self.client_socket.recv(4)
            if not header:
                self.connected = False
                raise Exception("No response received")
                
            msg_len = struct.unpack('!I', header)[0]
            response = self.client_socket.recv(msg_len)
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="LIST",
                name="user_list",
                response_time=total_time,
                response_length=len(response),
                exception=None,
            )
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="LIST",
                name="user_list",
                response_time=total_time,
                response_length=0,
                exception=e,
            )
            self.connected = False
