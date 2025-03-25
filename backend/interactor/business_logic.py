import sys
import os
import bcrypt

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.interfaces.db_interface import MongoDBInterface
from datetime import datetime
from backend.interfaces.business_logic_interface import BusinessLogicInterface

class BusinessLogic(BusinessLogicInterface):
    def __init__(self, db_operations: MongoDBInterface):
        self.db_operations = db_operations

    def create_user(self, user_name, user_password) -> bool:
        # Hash the password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user_password.encode('utf-8'), salt)
        
        user_data = {
            "user_name": user_name,
            "user_password": hashed_password,  # Store the hashed password
            "view_count": 5, # default view count of 5
            "log_off_time": None # default log off time of None
        }

        print(f"Inserting user: {user_data}")
        result = self.db_operations.insert("users", user_data)
        return result
    
    def delete_user(self, user_name) -> bool:
        try:
            # First, delete all messages sent by or received by this user
            sent_query = {"sender": user_name}
            received_query = {"receiver": user_name}
            
            # Delete messages sent by this user
            sent_result = self.db_operations.delete("messages", sent_query)
            if sent_result is not None and sent_result > 0:
                print(f"Deleted {sent_result} messages sent by user: {user_name}")
            
            # Delete messages received by this user
            received_result = self.db_operations.delete("messages", received_query)
            if received_result is not None and received_result > 0:
                print(f"Deleted {received_result} messages received by user: {user_name}")
            
            # Finally, delete the user
            user_query = {"user_name": user_name}
            user_result = self.db_operations.delete("users", user_query)
            
            if user_result is not None and user_result > 0:
                print(f"User deleted: {user_name}")
                return True
            else:
                print(f"User deletion failed: {user_name}")
                return False
        except Exception as e:
            print(f"Error deleting user and messages: {e}")
            return False

    def get_user(self, user_name) -> dict:
        query = {"user_name": user_name}
        user_docs = self.db_operations.read("users", query)
        # Return the first user document if found, otherwise empty dict
        print(f"Getting user document: {user_docs}")
        return user_docs[0] if user_docs else {}
    
    def get_all_users(self) -> list:
        docs = self.db_operations.read("users", {}) or []
        user_list = [doc["user_name"] for doc in docs]
        print(f"User list: {user_list}")
        return user_list
    
    def login_user(self, user_name, user_password) -> bool:
        print(f"Logging in user: {user_name}")  # Removed password from print for security
        query = {"user_name": user_name}
        user_doc = self.db_operations.read("users", query)
        
        if len(user_doc) == 0:
            return False
            
        # Compare the hashed passwords
        stored_password = user_doc[0].get("user_password")
        
        # Ensure stored_password is bytes
        if not isinstance(stored_password, bytes):
            print(f"Error: stored password is not bytes, it's {type(stored_password)}")
            return False
            
        try:
            # Ensure user_password is encoded to bytes before checking
            password_bytes = user_password.encode('utf-8') if isinstance(user_password, str) else user_password
            if not bcrypt.checkpw(password_bytes, stored_password):
                return False
                
            print(f"Login successful for user: {user_name}")
            return True
        except Exception as e:
            print(f"Error checking password: {e}")
            return False
    
    def send_message(self, sender, receiver, message) -> bool:
        check_receiver = self.get_user(receiver)
        if check_receiver is None:
            print(f"Receiver {receiver} not found")
            return False
        message_data = {
            "sender": sender,
            "receiver": receiver,
            "message": message,
            "timestamp": datetime.now()
        }
        try:
            result = self.db_operations.insert("messages", message_data)
            return result is not None
        except Exception:
            return False
    
    # this needs to be constantly called to update the view count via websocket?
    def get_messages(self, user) -> dict:
        messages_dict = {}
        
        # Query for messages where the user is the sender
        query = {"sender": user}
        sent_messages = self.db_operations.read("messages", query) or []
        
        for message in sent_messages:
            receiver = message["receiver"]
            if receiver not in messages_dict:
                messages_dict[receiver] = []
            messages_dict[receiver].append(message)
        
        # Query for messages where the user is the receiver
        query = {"receiver": user}
        received_messages = self.db_operations.read("messages", query) or []
        
        for message in received_messages:
            sender = message["sender"]
            if sender not in messages_dict:
                messages_dict[sender] = []
            messages_dict[sender].append(message)
        
        # Sort messages for each user by timestamp
        for user in messages_dict:
            messages_dict[user] = sorted(messages_dict[user], key=lambda x: x["timestamp"])
        
        print(f"Messages: {messages_dict}")
        return messages_dict
    
    def delete_message(self, message:str, timestamp:str, sender:str, receiver:str) -> bool:
        from datetime import datetime, timedelta
        try:
            print(f"Deleting message: {message} from {sender} to {receiver} at {timestamp}")
            
            # Try to parse the timestamp string in different formats
            timestamp_dt = None
            
            # First try ISO format (with T separator)
            if 'T' in timestamp:
                try:
                    timestamp_dt = datetime.fromisoformat(timestamp)
                except ValueError:
                    pass
            
            # If that fails, try standard format
            if timestamp_dt is None:
                try:
                    timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # If both parsing attempts fail, try to find the message by other criteria
                    print(f"Could not parse timestamp: {timestamp}")
                    timestamp_dt = None
            
            print(f"Timestamp datetime: {timestamp_dt}")
            
            # Create query with required fields
            query = {
                "message": message,
                "sender": sender,
            }
            
            # Add receiver to query if provided
            if receiver:
                query["receiver"] = receiver
                
            # Add timestamp to query if we could parse it
            if timestamp_dt:
                # Create a timestamp range to account for millisecond differences
                # This will match messages within the same second
                start_time = timestamp_dt - timedelta(seconds=1)
                end_time = timestamp_dt + timedelta(seconds=1)
                
                query["timestamp"] = {
                    "$gte": start_time.isoformat(),
                    "$lt": end_time.isoformat()
                }

            print(f"Query: {query}")
            
            result = self.db_operations.delete("messages", query)
            if result is not None and result > 0:
                print(f"Message deleted: {message} from {sender} to {receiver} at {timestamp}")
                return True
            else:
                print(f"Message failed to delete: {message} from {sender} to {receiver} at {timestamp}")
                # Try a more lenient query without timestamp if the first attempt failed
                if timestamp_dt and "timestamp" in query:
                    del query["timestamp"]
                    print(f"Trying more lenient query: {query}")
                    result = self.db_operations.delete("messages", query)
                    if result is not None and result > 0:
                        print(f"Message deleted with lenient query: {message} from {sender} to {receiver}")
                        return True
                return False
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False
        
    def update_view_count(self, view_count, username) -> bool:
        query = {"user_name": username}
        update_values = {"view_count": view_count}
        try:
            result = self.db_operations.update("users", query, update_values)
            if result is not None and result > 0:
                print(f"View count updated for user: {username}")
                return True
            else:
                print(f"View count update failed for user: {username}")
                return False
        except Exception as e:
            print(f"Error updating view count: {e}")
            return False
        
    def update_log_off_time(self, user_name) -> bool:
        query = {"user_name": user_name}
        update_values = {"log_off_time": datetime.now()}
        result = self.db_operations.update("users", query, update_values)
        if result is not None and result > 0:
            print(f"Log off time updated for user: {user_name}")
            return True
        else:
            print(f"Log off time update failed for user: {user_name}")
            return False
        
if __name__ == "__main__":
    from backend.database.mongo_operations import MongoOperation
    business_logic = BusinessLogic(MongoOperation())
    # print(business_logic.create_user("John Doe", "john.doe@example.com", "password123"))
    # print(business_logic.get_user("john.doe@example.com"))
    # print(business_logic.send_message("John Doe", "Jane Smith", "Hello, how are you?"))
    print(business_logic.get_messages("John Doe"))
    print(business_logic.update_view_count(10, "john.doe@example.com"))
