# Chat Application

A Python-based chat application with support for both custom wire protocol and JSON messaging.

## Features

- User registration and authentication
- Real-time messaging
- Message history
- Online user list
- Configurable message view count
- Support for both custom wire protocol and JSON
- Environment variable configuration

## Prerequisites

- Python 3.8 or higher
- MongoDB
- pip (Python package installer)

## Installation

1. Activate the virtual environment:
```bash
source 2620_chatapp_env/bin/activate
```

1. Install backend dependencies in the backend directory:
```bash
pip install -r requirements.txt
```





## Protocol Selection

### RPC (Default)

To use RPC:
1. In `routes.py`, set:
```python
protocol_of_choice = rpc_protocol
```

2. In `client.py`, set:
```python
app = ClientApp(rpc_protocol, rpc_handler)
```


### Wire Protocol

To use Wire Protocol:
1. In `routes.py`, set:
```python
protocol_of_choice = wire_protocol
```

2. In `client.py`, set:
```python
app = ClientApp(wire_protocol, socket_handler)
```

### JSON Protocol

To use JSON Protocol:
1. In `routes.py`, set:
```python
protocol_of_choice = json_protocol
```

2. In `client.py`, set:
```python
app = ClientApp(json_protocol, socket_handler)
```




## Configuration (only for custome wire protocol or json)

The application supports configuration through environment variables:

- `CHAT_APP_HOST`: Server host address (default: '0.0.0.0')
- `CHAT_APP_PORT`: Server port number (default: 8081)



## Running the Application

### Starting the Server

1. Make sure the virtual environment is active

2. Navigate to the backend directory:
```bash
cd backend
```

3. Start the server:
```bash
python controller/routes.py
```

The server will start and listen for incoming connections.

### Starting the Client

1. Navigate to the client directory:
```bash
cd client
```

2. Launch the client application:
```bash
python client.py
```

The client GUI will appear with a login screen.
