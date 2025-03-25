from abc import ABC, abstractmethod

class BusinessLogicInterface(ABC):
    @abstractmethod
    def create_user(self, user_name, user_password) -> bool:
        """Create a new user with the provided details."""
        pass

    @abstractmethod
    def delete_user(self, user_name) -> bool:
        """Delete a user by their username."""
        pass

    @abstractmethod
    def get_user(self, user_name) -> dict:
        """Retrieve a user by their username."""
        pass

    @abstractmethod
    def get_all_users(self) -> list:
        """Retrieve all users from the database."""
        pass

    @abstractmethod
    def login_user(self, user_name, user_password) -> bool:
        """Login a user with the provided details."""
        pass

    @abstractmethod
    def send_message(self, sender, receiver, message) -> bool:
        """Send a message from the sender to the receiver."""
        pass

    @abstractmethod
    def get_messages(self, user) -> dict:
        """Retrieve all messages for a user."""
        pass

    @abstractmethod
    def delete_message(self, message:str, timestamp:str, sender:str, receiver:str) -> bool:
        """Delete a message by its ID."""
        pass

    @abstractmethod
    def update_view_count(self, view_count, user_email) -> bool:
        """Update the view count for a specified user."""
        pass

    @abstractmethod
    def update_log_off_time(self, user_name) -> bool:
        """Update the log off time for a specified user."""
        pass
