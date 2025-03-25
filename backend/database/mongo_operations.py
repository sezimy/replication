from pymongo import MongoClient
from interfaces.db_interface import MongoDBInterface
from pymongo.errors import ConnectionFailure, OperationFailure

class MongoOperation(MongoDBInterface):
    def __init__(self):
        try:
            self.client = MongoClient('mongodb+srv://dyang:tJwvDN1gD0Cqkjpq@chatapp.42cn2.mongodb.net/?tlsAllowInvalidCertificates=true')
            # Verify connection
            self.client.admin.command('ping')
            self.db = self.client['ChatApp']
            print("Successfully connected to MongoDB")
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
        except OperationFailure as e:
            print(f"Authentication failed: {e}")
            raise

    def insert(self, collection_name, document):
        try:
            collection = self.db[collection_name]
            result = collection.insert_one(document)
            
            if result.acknowledged:
                print(f"Successfully inserted document with ID: {result.inserted_id}")
                return result.inserted_id
            else:
                print("Insert operation was not acknowledged")
                return False
                
        except Exception as e:
            print(f"Error inserting document: {e}")
            return False

    def read(self, collection_name, query):
        collection = self.db[collection_name]
        documents = collection.find(query)
        return list(documents)

    def update(self, collection_name, query, update_values):
        collection = self.db[collection_name]
        result = collection.update_one(query, {'$set': update_values})
        if result.modified_count > 0:
            print(f"Successfully updated {result.modified_count} documents")
        else:
            print("No documents were updated")
        return result.modified_count

    def delete(self, collection_name, query):
        collection = self.db[collection_name]
        result = collection.delete_one(query)
        if result.deleted_count > 0:
            print(f"Successfully deleted {result.deleted_count} documents")
        else:
            print("No documents were deleted")
        return result.deleted_count
