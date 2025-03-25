import json
import os
from datetime import datetime
import threading
import base64
from backend.interfaces.db_interface import MongoDBInterface

class FileOperation(MongoDBInterface):
    def __init__(self):
        # Create data directory if it doesn't exist
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create collection files if they don't exist
        self.collections = {
            'users': os.path.join(self.data_dir, 'users.json'),
            'messages': os.path.join(self.data_dir, 'messages.json')
        }
        
        # Initialize empty collections if files don't exist
        for collection, file_path in self.collections.items():
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)
        
        # Lock for thread safety
        self.locks = {
            'users': threading.Lock(),
            'messages': threading.Lock()
        }
        
        print("Successfully initialized file-based storage")

    def _load_collection(self, collection_name):
        """Load a collection from file"""
        file_path = self.collections.get(collection_name)
        if not file_path:
            print(f"Collection {collection_name} does not exist")
            return []
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                # Convert base64 encoded bytes back to bytes objects
                for doc in data:
                    for key, value in doc.items():
                        if isinstance(value, dict) and value.get('__type__') == 'bytes':
                            doc[key] = base64.b64decode(value.get('data', ''))
                return data
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {file_path}")
            return []
        except Exception as e:
            print(f"Error loading collection {collection_name}: {e}")
            return []

    def _save_collection(self, collection_name, data):
        """Save a collection to file"""
        file_path = self.collections.get(collection_name)
        if not file_path:
            print(f"Collection {collection_name} does not exist")
            return False
            
        try:
            with open(file_path, 'w') as f:
                # Handle datetime objects for JSON serialization
                json.dump(data, f, default=self._json_serial, indent=2)
            return True
        except Exception as e:
            print(f"Error saving collection {collection_name}: {e}")
            return False
    
    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, str) and obj.find('T') > 0 and obj.find(':') > 0:
            # This looks like an ISO format datetime string, return it as is
            return obj
        if isinstance(obj, bytes):
            # Store bytes as base64 encoded string with type information
            return {
                "__type__": "bytes",
                "data": base64.b64encode(obj).decode('ascii')
            }
        raise TypeError(f"Type {type(obj)} not serializable")

    def insert(self, collection_name, document):
        """Insert a document into a collection"""
        with self.locks[collection_name]:
            data = self._load_collection(collection_name)
            
            # Add a unique ID if not present
            if '_id' not in document:
                # Simple ID generation - timestamp + count
                document['_id'] = f"{datetime.now().timestamp()}_{len(data)}"
                
            data.append(document)
            success = self._save_collection(collection_name, data)
            
            if success:
                print(f"Successfully inserted document with ID: {document['_id']}")
                return document['_id']
            else:
                print("Insert operation failed")
                return False

    def read(self, collection_name, query=None):
        """Read documents from a collection that match the query"""
        if query is None:
            query = {}
            
        with self.locks[collection_name]:
            data = self._load_collection(collection_name)
            
            if not query:  # If query is empty, return all documents
                return data
            
            # Filter documents based on query
            result = []
            for doc in data:
                match = True
                for key, value in query.items():
                    # Handle special MongoDB-like operators
                    if isinstance(value, dict) and any(k.startswith('$') for k in value.keys()):
                        for op, op_value in value.items():
                            if op == '$gte' and key in doc:
                                if isinstance(doc[key], str) and isinstance(op_value, datetime):
                                    # Handle string to datetime comparison
                                    doc_date = datetime.fromisoformat(doc[key])
                                    match = match and doc_date >= op_value
                                else:
                                    match = match and doc[key] >= op_value
                            elif op == '$lt' and key in doc:
                                if isinstance(doc[key], str) and isinstance(op_value, datetime):
                                    # Handle string to datetime comparison
                                    doc_date = datetime.fromisoformat(doc[key])
                                    match = match and doc_date < op_value
                                else:
                                    match = match and doc[key] < op_value
                    elif key in doc:
                        match = match and doc[key] == value
                    else:
                        match = False
                
                if match:
                    result.append(doc)
            
            return result

    def update(self, collection_name, query, update_values):
        """Update documents in a collection that match the query"""
        with self.locks[collection_name]:
            data = self._load_collection(collection_name)
            modified_count = 0
            
            for doc in data:
                match = True
                for key, value in query.items():
                    if key in doc:
                        match = match and doc[key] == value
                    else:
                        match = False
                        
                if match:
                    for key, value in update_values.items():
                        doc[key] = value
                    modified_count += 1
                    
            if modified_count > 0:
                success = self._save_collection(collection_name, data)
                if success:
                    print(f"Successfully updated {modified_count} documents")
                else:
                    print("Update operation failed")
                    modified_count = 0
            else:
                print("No documents were updated")
                
            return modified_count

    def delete(self, collection_name, query):
        """Delete documents from a collection that match the query"""
        try:
            with self.locks[collection_name]:
                # Load current data
                collection = self._load_collection(collection_name)
                if not collection:
                    print(f"No documents in collection {collection_name}")
                    return 0
                
                # Process query to handle ISO format timestamps
                processed_query = self._process_query_timestamps(query)
                
                # Count documents before deletion
                original_count = len(collection)
                
                # Filter out documents that match the query
                filtered_collection = []
                for doc in collection:
                    if not self._matches_query(doc, processed_query):
                        filtered_collection.append(doc)
                
                # Count how many documents were deleted
                deleted_count = original_count - len(filtered_collection)
                
                if deleted_count > 0:
                    # Save the filtered collection back to the file
                    success = self._save_collection(collection_name, filtered_collection)
                    if success:
                        print(f"Deleted {deleted_count} documents from {collection_name}")
                        return deleted_count
                    else:
                        print("Delete operation failed")
                        return 0
                else:
                    print(f"No documents were deleted")
                    return 0
                    
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return None
            
    def _process_query_timestamps(self, query):
        """Process query to handle ISO format timestamps"""
        from datetime import datetime
        import copy
        
        processed_query = copy.deepcopy(query)
        
        # Check if there's a timestamp field with range operators
        if "timestamp" in processed_query and isinstance(processed_query["timestamp"], dict):
            timestamp_query = processed_query["timestamp"]
            
            # Process $gte operator
            if "$gte" in timestamp_query and isinstance(timestamp_query["$gte"], str):
                try:
                    # If it's already an ISO string, keep it as is
                    datetime.fromisoformat(timestamp_query["$gte"])
                except ValueError:
                    # If it's not a valid ISO string, try to convert it
                    try:
                        dt = datetime.strptime(timestamp_query["$gte"], "%Y-%m-%d %H:%M:%S")
                        timestamp_query["$gte"] = dt.isoformat()
                    except ValueError:
                        pass
            
            # Process $lt operator
            if "$lt" in timestamp_query and isinstance(timestamp_query["$lt"], str):
                try:
                    # If it's already an ISO string, keep it as is
                    datetime.fromisoformat(timestamp_query["$lt"])
                except ValueError:
                    # If it's not a valid ISO string, try to convert it
                    try:
                        dt = datetime.strptime(timestamp_query["$lt"], "%Y-%m-%d %H:%M:%S")
                        timestamp_query["$lt"] = dt.isoformat()
                    except ValueError:
                        pass
                        
        return processed_query
            
    def _matches_query(self, doc, query):
        """Check if a document matches the query"""
        from datetime import datetime
        
        for key, value in query.items():
            # Skip if the key is not in the document
            if key not in doc:
                return False
                
            # Handle range operators for timestamps
            if isinstance(value, dict) and key == "timestamp":
                doc_timestamp = doc[key]
                
                # Convert string timestamp to datetime for comparison
                if isinstance(doc_timestamp, str):
                    try:
                        doc_dt = datetime.fromisoformat(doc_timestamp)
                    except ValueError:
                        # If we can't parse the timestamp, it doesn't match
                        return False
                else:
                    doc_dt = doc_timestamp
                
                # Check each operator
                for op, op_value in value.items():
                    if op == "$gte":
                        # Convert operator value to datetime if it's a string
                        if isinstance(op_value, str):
                            try:
                                op_dt = datetime.fromisoformat(op_value)
                            except ValueError:
                                return False
                        else:
                            op_dt = op_value
                            
                        if doc_dt < op_dt:
                            return False
                    elif op == "$lt":
                        # Convert operator value to datetime if it's a string
                        if isinstance(op_value, str):
                            try:
                                op_dt = datetime.fromisoformat(op_value)
                            except ValueError:
                                return False
                        else:
                            op_dt = op_value
                            
                        if doc_dt >= op_dt:
                            return False
            # Handle exact match for other fields
            elif doc[key] != value:
                return False
                
        return True
