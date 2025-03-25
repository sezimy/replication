import socket
import struct
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import json
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # add parent directory to python path

from interfaces.client_serialization_interface import ClientSerializationInterface
from interfaces.client_communication_interface import ClientCommunicationInterface

# import only JSON protocol
from protocol.client_json_protocol import ClientJsonProtocol

# import only socket handler
from network.client_socket_handler import ClientSocketHandler

from enum import Enum

class ProtocolType(Enum):
    JSON = "json"

class ClientApp:
    def __init__(self, serialization_interface: ClientSerializationInterface, communication_interface: ClientCommunicationInterface):
        # Choose communication handler based on protocol
        self.comm_handler = communication_interface
        
        host = os.getenv('CHAT_APP_HOST', '0.0.0.0')
        
        # Try connecting to each replica server in order
        connected = False
        for port in [8091, 8092, 8093]:  # Try all replica client ports
            try:
                print(f"Trying to connect to server at {host}:{port}")
                self.comm_handler.start_server(host, port)
                connected = True
                print(f"Successfully connected to server at {host}:{port}")
                break
            except Exception as e:
                print(f"Failed to connect to {host}:{port}: {e}")
        
        if not connected:
            print("Could not connect to any server. Please make sure at least one server is running.")
            sys.exit(1)
        
        self.username = ""
        self.password = ""
        self.root = tk.Tk()
        self.root.title("Chat Client")
        # Add protocol for window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.serialization_interface = serialization_interface
        self.protocol_type = ProtocolType.JSON
        self.login_screen()
        self.user_list = []
        self.last_log_off = None
        self.view_count = 5
        self.messages_by_user = {}  # Store messages by user
        self.periodic_check_messages()

    def read_exact(self, n):
        data = b''
        while len(data) < n:
            packet = self.comm_handler.get_message(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def login_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # Create main frame with padding
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(expand=True)
        
        # Title
        title = tk.Label(main_frame, text="Chat Client", font=('Arial', 16, 'bold'))
        title.pack(pady=(0, 20))
        
        # Username section
        tk.Label(main_frame, text="Username").pack()
        self.username_entry = tk.Entry(main_frame)
        self.username_entry.pack()
        self.username_error = tk.Label(main_frame, text="", fg='red', font=('Arial', 8))
        self.username_error.pack()
        
        # Password section
        tk.Label(main_frame, text="Password").pack()
        self.password_entry = tk.Entry(main_frame, show="*")
        self.password_entry.pack()
        self.password_error = tk.Label(main_frame, text="", fg='red', font=('Arial', 8))
        self.password_error.pack()
        
        # Requirements info
        requirements = (
            "Username requirements:\n"
            "• Only letters and numbers\n"
            "• No spaces\n"
            "• 3-20 characters\n\n"
            "Password requirements:\n"
            "• At least 8 characters\n"
            "• At least one number\n"
            "• At least one uppercase letter\n"
            "• No spaces"
        )
        tk.Label(main_frame, text=requirements, justify=tk.LEFT, 
                font=('Arial', 8), fg='gray').pack(pady=10)
        
        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Login", command=self.login).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Register", command=self.register).pack(side=tk.LEFT, padx=5)

    def validate_username(self, username):
        """Validate username according to requirements"""
        import re
        if not 3 <= len(username) <= 20:
            return False, "Username must be 3-20 characters long"
        if not username.isalnum():
            return False, "Username can only contain letters and numbers"
        if ' ' in username:
            return False, "Username cannot contain spaces"
        return True, ""

    def validate_password(self, password):
        """Validate password according to requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if ' ' in password:
            return False, "Password cannot contain spaces"
        return True, ""

    def chat_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Configure the main window
        self.root.configure(bg='#36393f')
        self.root.geometry("1000x600")
        
        # Create main container
        main_container = tk.Frame(self.root, bg='#36393f')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create sidebar for contacts
        sidebar = tk.Frame(main_container, width=200, bg='#2f3136')
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Sidebar header
        tk.Label(sidebar, text="Conversations", bg='#2f3136', fg='white', font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Add search frame only if we have users
        print(f"User list before rendering bar: {self.user_list}")
        search_frame = ttk.Frame(sidebar)
        search_frame.pack(fill='x', padx=5, pady=5)
        
        # Create StringVar to track changes
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_users)
        
        # Create combobox with the StringVar
        self.user_search = ttk.Combobox(search_frame, 
                                       values=self.user_list,
                                       textvariable=self.search_var)
        self.user_search.pack(fill='x')
        self.user_search.bind('<<ComboboxSelected>>', self.on_user_selected)
        
        # Style the combobox to match theme
        style = ttk.Style()
        style.configure('TCombobox', 
                       fieldbackground='#40444b',
                       background='#2f3136',
                       foreground='white')
        
        # Contacts list frame with scrollbar
        contacts_frame = tk.Frame(sidebar, bg='#2f3136')
        contacts_frame.pack(fill=tk.BOTH, expand=True)
        
        self.contacts_list = tk.Listbox(contacts_frame, bg='#2f3136', fg='white', 
                                       selectmode=tk.SINGLE, relief=tk.FLAT,
                                       font=('Arial', 10))
        self.contacts_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.contacts_list.bind('<<ListboxSelect>>', self.on_contact_select)
        
        # Add delete account button at the bottom of sidebar
        delete_account_btn = tk.Button(
            sidebar,
            text="Delete Account",
            command=self.delete_account,
            bg='#ED4245',  # Discord's danger red
            fg='black',
            relief=tk.FLAT,
            font=('Arial', 10),
            padx=10,
            pady=5,
            activebackground='#c03537',  # Darker red for hover
            activeforeground='white'
        )
        delete_account_btn.pack(side=tk.BOTTOM, pady=10)
        
        # Add stats frame above delete button
        stats_frame = tk.Frame(sidebar, bg='#2f3136')
        stats_frame.pack(side=tk.BOTTOM, fill='x', padx=5, pady=5)
        
        # Last log-off time label
        self.log_off_label = tk.Label(
            stats_frame, 
            text="Last log-off: Never",
            bg='#2f3136',
            fg='white',
            font=('Arial', 8),
            wraplength=180
        )
        self.log_off_label.pack(fill='x', pady=2)
        
        # View count frame
        view_count_frame = tk.Frame(stats_frame, bg='#2f3136')
        view_count_frame.pack(fill='x')
        
        # View count label and entry
        self.view_count_label = tk.Label(
            view_count_frame,
            text=f"View Count: {self.view_count}",
            bg='#2f3136',
            fg='white',
            font=('Arial', 8)
        )
        self.view_count_label.pack(side=tk.LEFT, pady=2)
        
        # Update view count button
        self.view_count_entry = tk.Entry(view_count_frame, width=5)
        self.view_count_entry.pack(side=tk.LEFT, padx=5)
        self.view_count_entry.insert(0, str(self.view_count))
        
        update_btn = tk.Button(
            view_count_frame,
            text="Update",
            command=self.update_view_count,
            bg='#5865f2',
            fg='black',
            font=('Arial', 8),
            relief=tk.FLAT
        )
        update_btn.pack(side=tk.RIGHT)
        
        # Chat area container
        chat_container = tk.Frame(main_container, bg='#36393f')
        chat_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Chat header
        self.chat_header = tk.Label(chat_container, text="Select a conversation", 
                                   bg='#36393f', fg='white', font=('Arial', 12, 'bold'))
        self.chat_header.pack(fill=tk.X, pady=10)
        
        # Chat messages area with scrollbar
        self.chat_area = tk.Text(chat_container, bg='#36393f', fg='white', 
                                wrap=tk.WORD, state='disabled')
        scrollbar = tk.Scrollbar(chat_container, command=self.chat_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10)
        self.chat_area.configure(yscrollcommand=scrollbar.set)
        
        # Message input area
        input_frame = tk.Frame(chat_container, bg='#36393f')
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.message_entry = tk.Entry(input_frame, bg='#40444b', fg='white', 
                                     relief=tk.FLAT, font=('Arial', 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        
        send_button = tk.Button(input_frame, text="Send", command=self.send_message,
                               bg='#000080', fg='black', relief=tk.FLAT,
                               font=('Arial', 10), padx=15, pady=5,
                               activebackground='#4752c4', activeforeground='white')
        send_button.pack(side=tk.RIGHT)

    def on_contact_select(self, event):
        selection = self.contacts_list.curselection()
        if selection:
            contact = self.contacts_list.get(selection[0])
            self.current_contact = contact
            self.chat_header.config(text=f"Chat with {contact}")
            self.display_conversation(contact)

    def display_conversation(self, contact):
        self.chat_area.config(state='normal')
        self.chat_area.delete(1.0, tk.END)
        
        if contact in self.messages_by_user:
            messages = self.messages_by_user[contact]
            
            # Split messages into before and after last_log_off
            messages_before = []
            messages_after = []
            
            for msg in messages:
                # Extract timestamp from message format "[2024-03-14 12:34:56] [sender -> receiver]: content"
                msg_time_str = msg[1:20]
                try:
                    msg_time = datetime.strptime(msg_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    if self.last_log_off is None or msg_time <= self.last_log_off:
                        messages_before.append(msg)
                    else:
                        messages_after.append(msg)
                except ValueError:
                    # If there's any issue parsing the timestamp, treat as an old message
                    messages_before.append(msg)
            
            # Display all messages before last_log_off
            for msg in messages_before:
                self.display_message(msg)
            
            # If there are messages after last_log_off
            if messages_after:
                # Add a visual separator
                separator = tk.Frame(self.chat_area, height=2, bg='#5865f2')
                self.chat_area.window_create(tk.END, window=separator, stretch=True)
                self.chat_area.insert(tk.END, '\nNew messages since last login:\n\n')
                
                # Display first batch of messages based on view_count
                self.current_message_index = 0
                self.remaining_messages = messages_after
                self.display_next_batch()
        
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

    def display_next_batch(self):
        """Display next batch of messages based on view_count"""
        if not hasattr(self, 'remaining_messages'):
            return
            
        end_index = min(self.current_message_index + self.view_count, len(self.remaining_messages))
        current_batch = self.remaining_messages[self.current_message_index:end_index]
        
        # Display current batch
        for msg in current_batch:
            self.display_message(msg)
        
        # Update current index
        self.current_message_index = end_index
        
        # If there are more messages, show the "View More" button
        if self.current_message_index < len(self.remaining_messages):
            self.show_view_more_button()

    def display_message(self, msg):
        """Display a single message with delete button"""
        msg_frame = tk.Frame(self.chat_area, bg='#36393f')
        self.chat_area.window_create(tk.END, window=msg_frame)
        
        # Add message text
        msg_label = tk.Label(msg_frame, text=msg, bg='#36393f', fg='white',
                            wraplength=500, justify=tk.LEFT)
        msg_label.pack(side=tk.LEFT, pady=2)
        
        # Add delete button
        delete_btn = tk.Button(
            msg_frame, 
            text="×", 
            bg='#36393f', 
            fg='black',
            font=('Arial', 8),
            relief=tk.FLAT,
            command=lambda m=msg: self.handle_delete_message(m, self.current_contact)
        )
        delete_btn.pack(side=tk.RIGHT, padx=5)
        
        self.chat_area.insert(tk.END, '\n')

    def show_view_more_button(self):
        """Create and display the View More button"""
        remaining_count = len(self.remaining_messages) - self.current_message_index
        
        button_frame = tk.Frame(self.chat_area, bg='#36393f')
        self.chat_area.window_create(tk.END, window=button_frame)
        
        view_more_btn = tk.Button(
            button_frame,
            text=f"View More ({remaining_count} messages remaining)",
            command=self.display_next_batch,
            bg='#5865f2',
            fg='black',
            relief=tk.FLAT,
            font=('Arial', 10),
            padx=10,
            pady=5,
            activebackground='#4752c4',
            activeforeground='white'
        )
        view_more_btn.pack(pady=10)
        
        # Remove the old button before displaying new messages
        def display_and_remove():
            button_frame.destroy()
            self.display_next_batch()
        
        view_more_btn.configure(command=display_and_remove)
        self.chat_area.insert(tk.END, '\n')

    def update_contacts_list(self):
        self.contacts_list.delete(0, tk.END)
        for contact in sorted(self.messages_by_user.keys()):
            self.contacts_list.insert(tk.END, contact)

    def serialize_message(self, msg_type, lst):
        return self.serialization_interface.serialize_message(msg_type, lst)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        # Validate username and password
        username_valid, username_error = self.validate_username(username)
        password_valid, password_error = self.validate_password(password)
        
        # Clear previous error messages
        self.username_error.config(text="")
        self.password_error.config(text="")
        
        if not username_valid:
            self.username_error.config(text=username_error)
            return
        if not password_valid:
            self.password_error.config(text=password_error)
            return
        
        data = self.serialize_message('L', [username, password])
        print(f"Sending login: {len(data)} bytes")  
        # Proceed with login
        self.comm_handler.send_message(data)
        response = self.read_json_response()
        
        # Handle potential None response from server
        if not response:
            messagebox.showerror("Error", "Server did not respond. Please try again later.")
            return
        
        # Handle both list and dictionary response formats
        if isinstance(response, list) and len(response) > 0:
            resp = response[0]
        elif isinstance(response, dict):
            resp = response
        else:
            print(f"Unexpected response format: {type(response)}")
            messagebox.showerror("Error", "Received invalid response format from server")
            return
            
        if resp['type'] == 'S':
            self.username = username
            self.password = password
            messagebox.showinfo("Success", resp['payload'])
            
            # First request the user list
            self.request_user_list()
            
            # Wait for the user list response
            user_list_response = self.read_json_response()
            if user_list_response:
                if isinstance(user_list_response, dict):
                    self.receive_message_helper(user_list_response.get('type'), user_list_response.get('payload'))
                elif isinstance(user_list_response, list):
                    for msg in user_list_response:
                        if isinstance(msg, dict):
                            self.receive_message_helper(msg.get('type'), msg.get('payload'))
            
            # Request user stats
            print("Requesting user stats")
            stats_request = self.serialize_message('GS', [username])
            print(f"Stats request: {stats_request}")
            self.comm_handler.send_message(stats_request)
            
            # Wait for the stats response
            print("Waiting for stats response...")
            stats_response = self.read_json_response()
            print(f"Raw stats response: {stats_response}")
            if stats_response:
                print(f"Received stats response type: {type(stats_response)}")
                if isinstance(stats_response, dict):
                    # Check if it's an error response
                    if stats_response.get('type') == 'E':
                        print(f"Error getting user stats: {stats_response.get('payload')}")
                        # Don't stop the login process for stats errors
                    else:
                        print(f"Processing stats response with type: {stats_response.get('type')}")
                        self.receive_message_helper(stats_response.get('type'), stats_response.get('payload'))
                elif isinstance(stats_response, list):
                    for msg in stats_response:
                        if isinstance(msg, dict):
                            # Check if it's an error response
                            if msg.get('type') == 'E':
                                print(f"Error getting user stats: {msg.get('payload')}")
                                # Don't stop the login process for stats errors
                            else:
                                print(f"Processing stats response with type: {msg.get('type')}")
                                self.receive_message_helper(msg.get('type'), msg.get('payload'))
            
            # Explicitly request messages after login
            print("Requesting messages after login")
            message_request = self.serialize_message('GM', [username])  # 'GM' for Get Messages
            self.comm_handler.send_message(message_request)
            
            # Wait for the message response
            print("Waiting for message response...")
            message_response = self.read_json_response()
            if message_response:
                print(f"Received message response: {type(message_response)}")
                # Process the message response
                if isinstance(message_response, dict):
                    self.receive_message_helper(message_response.get('type'), message_response.get('payload'))
                elif isinstance(message_response, list):
                    for msg in message_response:
                        if isinstance(msg, dict):
                            self.receive_message_helper(msg.get('type'), msg.get('payload'))
            
            # Switch to chat screen
            self.chat_screen()
            
            # Process additional data in the response
            for key, value in resp.items():
                if key not in ['type', 'payload']:
                    print(f"Received message: {key} with payload")
                    self.receive_message_helper(key, value)
        else:
            messagebox.showerror("Error", resp['payload'])

    def register(self):
        """Register a new user"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        # Validate username and password
        username_valid, username_error = self.validate_username(username)
        password_valid, password_error = self.validate_password(password)
        
        # Clear previous error messages
        self.username_error.config(text="")
        self.password_error.config(text="")
        
        if not username_valid:
            self.username_error.config(text=username_error)
            return
        if not password_valid:
            self.password_error.config(text=password_error)
            return
    
        print(f"Attempting to register user: {username}")
        # Send registration request
        request = self.serialize_message('R', [username, password])
        print(f"Sending request: {request}")
        self.comm_handler.send_message(request)
        print("Request sent, waiting for response...")
        
        # Add a timeout for the response
        max_wait_time = 10  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                # Update the UI while waiting
                self.root.update()
                
                # Try to read a response with a short timeout
                response = self.read_json_response()
                if response:  # Check if response is not empty
                    print(f"Received response: {response}")
                    
                    # Handle both list and dictionary response formats
                    if isinstance(response, list) and len(response) > 0:
                        resp = response[0]
                    elif isinstance(response, dict):
                        resp = response
                    else:
                        print(f"Unexpected response format: {type(response)}")
                        messagebox.showerror("Error", "Received invalid response format from server")
                        return
                    
                    if resp['type'] == 'S':
                        messagebox.showinfo("Success", resp['payload'])
                        return
                    else:
                        messagebox.showerror("Error", resp['payload'])
                        return
                
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
            except Exception as e:
                print(f"Error during registration: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("Error", f"Registration failed: {str(e)}")
                return
        
        # If we get here, we timed out
        print("Registration timed out after waiting for response")
        messagebox.showerror("Error", "Server did not respond in time. Please try again later.")

    def read_json_response(self) -> list:
        """Read complete JSON responses from the socket"""
        try:
            # Use the get_message method from our socket handler which already handles timeouts
            data = self.comm_handler.get_message(4096)
            if not data:
                # No data received, but don't print anything to avoid console flooding
                return []  # Return empty list instead of None
            
            # Try to decode the JSON
            try:
                decoded_data = data.decode('utf-8')
                
                # Check if we have multiple JSON objects in the response
                if decoded_data.count('}{') > 0:
                    print("Detected multiple JSON objects in response, splitting them")
                    # Split the response into individual JSON objects
                    json_objects = []
                    
                    # Insert proper delimiters between JSON objects
                    fixed_data = decoded_data.replace('}{', '},{')
                    
                    # Wrap in array brackets if not already present
                    if not fixed_data.startswith('['):
                        fixed_data = '[' + fixed_data
                    if not fixed_data.endswith(']'):
                        fixed_data = fixed_data + ']'
                    
                    try:
                        # Parse the fixed JSON array
                        json_objects = json.loads(fixed_data)
                        return json_objects
                    except json.JSONDecodeError as e:
                        print(f"Error decoding multiple JSON objects: {e}")
                        
                        # Fallback: try to parse each object individually
                        individual_jsons = []
                        parts = decoded_data.replace('}{', '}|{').split('|')
                        for part in parts:
                            try:
                                obj = json.loads(part)
                                individual_jsons.append(obj)
                            except json.JSONDecodeError:
                                print(f"Could not parse part: {part[:50]}...")
                        
                        return individual_jsons
                
                # Single JSON object
                response = json.loads(decoded_data)
                
                # Ensure we always return a consistent format
                # If it's a dict, keep it as is
                # If it's a list, keep it as is
                # Otherwise, wrap it in a list
                if isinstance(response, (dict, list)):
                    return response
                else:
                    print(f"Unexpected response type: {type(response)}")
                    return [{"type": "E", "payload": f"Unexpected response type: {type(response)}"}]
                    
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print(f"Received data: {data[:100]}...")  # Show first 100 chars
                return []
            
        except Exception as e:
            print(f"Error reading response: {e}")
            import traceback
            traceback.print_exc()
            return []

    def send_message(self):
        if not hasattr(self, 'current_contact'):
            messagebox.showerror("Error", "Please select a contact first")
            return
        
        message = self.message_entry.get()
        if not message:
            return
        
        recipient = self.current_contact
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data = self.serialize_message('M', [self.username, recipient, message])
        print(f"Sending message: {len(data)} bytes")
        self.comm_handler.send_message(data)

        # Add message to chat area immediately
        self.chat_area.config(state='normal')
        formatted_message = f"[{timestamp}] [{self.username} -> {recipient}]: {message}"
        self.chat_area.insert(tk.END, formatted_message + '\n')
        self.chat_area.see(tk.END)  # Scroll to bottom
        self.chat_area.config(state='disabled')

        # Store message in history
        if recipient not in self.messages_by_user:
            self.messages_by_user[recipient] = []
        self.messages_by_user[recipient].append(formatted_message)
        
        self.message_entry.delete(0, tk.END)

    def receive_message_helper(self, msg_type, payload):
        """Helper method to process received messages"""
        try:
            if msg_type == 'M':  # New message
                sender, message = payload
                self.handle_new_message(sender, message)
                
            elif msg_type == 'D':  # Delete message
                message_id = payload
                self.handle_delete_message(message_id)
                
            elif msg_type == 'U':  # User list
                print(f"User list: {payload}")
                self.handle_user_list(payload)
                
            elif msg_type == 'V':  # User stats
                time_str, view_count = self.serialization_interface.deserialize_user_stats(payload)
                self.view_count = view_count
                if time_str is None or time_str == "None":
                    self.last_log_off = None
                else:
                    try:
                        self.last_log_off = datetime.fromisoformat(time_str)
                    except Exception as e:
                        print(f"Error parsing datetime: {e}")
                        self.last_log_off = None
                
                # Update the UI
                self.update_stats_display()
                
            elif msg_type == 'S':  # For delete confirmation
                if self.serialization_interface.deserialize_success(payload) == "Message deleted":
                    messagebox.showinfo("Success", "Message deleted successfully")
                elif self.serialization_interface.deserialize_success(payload) == "User deleted successfully":
                    messagebox.showinfo("Success", "User deleted successfully")
                    self.show_login_window()
                
            elif msg_type == 'E':  # Error
                error_message = self.serialization_interface.deserialize_error(payload)
                messagebox.showerror("Error", error_message)
                
            elif msg_type == 'BM':  # Bulk Messages (new format)
                print(f"Received bulk messages: {len(payload)} threads")
                return self.handle_bulk_messages(payload)
                
            return True
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            return False

    def animate_message(self):
        self.chat_area.config(state='normal')
        end = self.chat_area.index(tk.END)
        
        # Get system background color
        bg_color = self.root.cget('bg')
        is_dark = self._is_dark_theme(bg_color)
        
        # Configure colors based on theme
        if is_dark:
            flash_colors = ["#404000", "#303000", None]  # Dark yellow to system background
        else:
            flash_colors = ["#ffff00", "#ffff88", None]  # Bright yellow to system background
        
        # Create animation tags
        self.chat_area.tag_config("flash", background=flash_colors[0])
        self.chat_area.tag_add("flash", f"{end}-2l", end)
        
        # Animate background color
        self.flash_animation(0, end, flash_colors)

    def flash_animation(self, count, position, colors):
        if count < len(colors):
            color = colors[count]
            if color is None:  # Reset to system background
                self.chat_area.tag_delete("flash")
            else:
                self.chat_area.tag_config("flash", background=color)
            self.root.after(150, lambda: self.flash_animation(count+1, position, colors))

    def _is_dark_theme(self, color):
        """Determine if the system theme is dark based on background color."""
        try:
            # Convert color name to RGB
            rgb = self.root.winfo_rgb(color)
            # Convert 16-bit RGB values to 8-bit
            r, g, b = rgb[0]//256, rgb[1]//256, rgb[2]//256
            # Calculate perceived brightness
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            return brightness < 128
        except:
            return False  # Default to light theme if color parsing fails

    def handle_bulk_messages(self, payload):
        """Handle bulk message delivery (stored messages)."""
        try:
            # Clear existing messages
            self.messages_by_user = {}
            
            # Process messages through the serialization interface
            messages_to_process = self.serialization_interface.deserialize_bulk_messages(payload, self.username, self.messages_by_user)
            
            # If the messages_by_user is empty but payload contains data, it might be raw data
            # This is a fallback in case the deserialize_bulk_messages didn't properly format the messages
            if not self.messages_by_user and payload:
                # Show a proper message window instead of raw data
                messagebox.showinfo("Messages Received", "You have received messages. Please select a contact to view them.")
            
            # Update UI on main thread
            self.root.after(0, self.update_chat_with_messages, messages_to_process)
            
        except Exception as e:
            print(f"Error handling bulk messages: {e}")
            # Don't show raw data to the user
            messagebox.showerror("Error", f"There was an error processing your messages: {e}")

    def update_chat_with_messages(self, messages):
        self.update_contacts_list()
        
        # Store current contact before updating
        current_contact = self.current_contact if hasattr(self, 'current_contact') else None
        
        # If we have a current contact, refresh their conversation
        if current_contact:
            self.chat_area.config(state='normal')
            self.chat_area.delete(1.0, tk.END)  # Clear existing messages
            self.display_conversation(current_contact)
            self.chat_area.config(state='disabled')
            self.chat_area.see(tk.END)  # Scroll to bottom

    def request_user_list(self):
        """Request the list of all users from the server"""
        self.comm_handler.send_message(self.serialization_interface.serialize_user_list())
    
    def handle_user_list(self, payload: bytes) -> list:
        """
        Deserialize the user list from the server response
        Returns a list of usernames
        """
        
        all_users = self.serialization_interface.deserialize_user_list(payload)
        self.user_list = [user for user in all_users if user != self.username]
        # Update the combobox with new user list
        if hasattr(self, 'user_search'):
            self.user_search['values'] = self.user_list
        return

    def create_search_frame(self):
        """Create a simple search frame for users"""
        search_frame = ttk.Frame(self.root)
        search_frame.pack(fill='x', padx=5, pady=5)
        
        # Create combobox that will show filtered results
        self.user_search = ttk.Combobox(search_frame, values=self.user_list)
        self.user_search.pack(fill='x')
        
        # Bind selection event
        self.user_search.bind('<<ComboboxSelected>>', self.on_user_selected)
        
    def on_user_selected(self, event):
        """Handle user selection from combobox"""
        selected_user = self.user_search.get()
        if selected_user and selected_user != self.username:  # Don't start chat with yourself
            # Add user to contacts if not already there
            if selected_user not in self.messages_by_user:
                self.messages_by_user[selected_user] = []
                self.update_contacts_list()
            # Select the user in contacts list
            idx = list(self.messages_by_user.keys()).index(selected_user)
            self.contacts_list.selection_clear(0, tk.END)
            self.contacts_list.selection_set(idx)
            self.on_contact_select(None)  # Update chat area

    def filter_users(self, *args):
        """Filter users based on search text"""
        search_text = self.search_var.get().lower()
        filtered_users = [
            user for user in self.user_list 
            if search_text in user.lower() and user != self.username
        ]
        self.user_search['values'] = filtered_users
        
        # Keep the dropdown open while typing
        if filtered_users:
            self.user_search.event_generate('<Down>')

    def delete_message(self, message_content, timestamp, sender, receiver):
        """Serialize and send a delete message request"""
        self.comm_handler.send_message(self.serialize_message('D', [message_content, timestamp, sender, receiver]))

    def handle_delete_message(self, message, contact):
        """Handle the deletion of a message"""
        if messagebox.askyesno("Delete Message", "Are you sure you want to delete this message?"):
            try:
                # Parse message format: [YYYY-MM-DD HH:MM:SS] [sender -> receiver]: content
                # Extract timestamp
                timestamp_end = message.find(']')
                if timestamp_end == -1:
                    raise ValueError("Invalid message format: Cannot find timestamp end")
                    
                timestamp = message[1:timestamp_end].strip()
                
                # Extract sender and receiver
                sender_receiver_part = message[timestamp_end+2:]  # Skip "] "
                sender_receiver_end = sender_receiver_part.find(']')
                if sender_receiver_end == -1:
                    raise ValueError("Invalid message format: Cannot find sender/receiver part")
                    
                sender_receiver = sender_receiver_part[1:sender_receiver_end].strip()  # Remove brackets
                
                # Split sender and receiver
                if " -> " in sender_receiver:
                    sender, receiver = sender_receiver.split(" -> ", 1)
                else:
                    # If format doesn't match, try to determine sender/receiver from context
                    sender = sender_receiver
                    receiver = contact if sender == self.username else self.username
                
                # Extract content
                content_start = sender_receiver_part.find(']: ')
                if content_start == -1:
                    raise ValueError("Invalid message format: Cannot find content start")
                    
                content = sender_receiver_part[content_start+3:].strip()  # Skip "]: "
                
                print(f"Deleting message: '{content}' from {sender} to {receiver} at {timestamp}")
                
                # Send delete request
                self.delete_message(content, timestamp, sender, receiver)
                
                # Remove from local storage
                if contact in self.messages_by_user:
                    if message in self.messages_by_user[contact]:
                        self.messages_by_user[contact].remove(message)
                
                # Refresh conversation
                self.display_conversation(contact)
                
            except Exception as e:
                print(f"Error parsing message for deletion: {e}")
                messagebox.showerror("Error", f"Could not delete message: {e}")

    def delete_account(self):
        """Send a request to delete the current user's account"""
        if messagebox.askyesno("Delete Account", 
                              "Are you sure you want to delete your account? This cannot be undone."):
            self.comm_handler.send_message(self.serialize_message('U', [self.username]))
            # The application will exit when we receive the success response from the server

    def update_view_count(self):
        try:
            new_count = int(self.view_count_entry.get())
            if new_count < 0:
                messagebox.showerror("Error", "View count must be positive")
                return
            self.comm_handler.send_message(self.serialize_message('W', [self.username, new_count]))
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def update_stats_display(self):
        """Update the stats labels with current values"""
        if hasattr(self, 'log_off_label'):
            log_off_text = f"Last log-off: {self.last_log_off or 'Never'}"
            self.log_off_label.config(text=log_off_text)
        
        if hasattr(self, 'view_count_label'):
            self.view_count_label.config(text=f"View Count: {self.view_count}")

    def on_closing(self):
        """Handle cleanup when window closes"""
        print("Cleaning up and closing client...")
        if self.username:  # If we're logged in, update log-off time
            try:
                # Update log-off time before closing
                data = self.serialize_message('O', {"username": self.username})  # Use dict format instead of list
                self.comm_handler.send_message(data)
            except:
                pass  # Don't prevent closing if this fails
        
        # Stop the communication handler
        self.comm_handler.stop_server()
        
        # Destroy the window
        self.root.destroy()

    def periodic_check_messages(self):
        """Periodically check for new messages"""
        try:
            self.check_messages()
        except Exception as e:
            # Only print serious errors, not timeouts
            if not isinstance(e, socket.timeout):
                print(f"Error in periodic check: {e}")
        finally:
            # Schedule the next check with a longer interval to reduce CPU usage
            self.root.after(2000, self.periodic_check_messages)  # Check every 2 seconds instead of 1

    def check_messages(self):
        """Check for new messages"""
        responses = self.read_json_response()
        if not responses:  # Handle empty list case
            return
            
        # Handle both list and dictionary response formats
        if isinstance(responses, dict):
            # Single response as dictionary
            msg_type = responses.get('type')
            payload = responses.get('payload')
            if msg_type and payload:
                # Only print actual messages, not empty responses
                if msg_type != 'E':  
                    print(f"Received message - Type: {msg_type}")
                self.receive_message_helper(msg_type, payload)
        elif isinstance(responses, list):
            # Multiple responses as list
            for response in responses:
                if isinstance(response, dict):
                    msg_type = response.get('type')
                    payload = response.get('payload')
                    if msg_type and payload:
                        # Only print actual messages, not empty responses
                        if msg_type != 'E':  
                            print(f"Received message - Type: {msg_type}")
                        if not self.receive_message_helper(msg_type, payload):
                            return

    def show_login_window(self):
        """
        Reset the client state and show the login screen after user deletion
        """
        self.username = ""
        self.password = ""
        self.messages_by_user = {}
        self.user_list = []
        self.last_log_off = None
        self.view_count = 5
        
        # Show the login screen
        self.login_screen()

if __name__ == "__main__":
    # Use only JSON protocol
    json_protocol = ClientJsonProtocol()
    
    # Use only socket handler
    socket_handler = ClientSocketHandler()
    
    # Create the app with JSON protocol
    app = ClientApp(json_protocol, socket_handler)
    app.root.mainloop()