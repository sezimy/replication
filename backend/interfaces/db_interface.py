from abc import ABC, abstractmethod

class MongoDBInterface(ABC):
    @abstractmethod
    def insert(self, collection_name, document):
        """Insert a document into a specified collection."""
        pass

    @abstractmethod
    def read(self, collection_name, query):
        """Read a document from a specified collection based on a query."""
        pass

    @abstractmethod
    def update(self, collection_name, query, update_values):
        """Update a document in a specified collection based on a query."""
        pass

    @abstractmethod
    def delete(self, collection_name, query):
        """Delete a document from a specified collection based on a query."""
        pass
