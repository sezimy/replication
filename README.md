# Distributed Chat Application

## Overview

This distributed chat application implements a primary-backup replication system that allows for fault tolerance and high availability. The system can withstand the failure of 2 servers while maintaining service availability and data consistency.

## Features

- **Fault Tolerance**: Continues operating even if servers fail
- **Primary-Backup Replication**: Ensures data consistency across all servers
- **Leader Election**: Automatically selects a new primary server if the current one fails
- **User Management**: Registration, login, and account deletion
- **Messaging**: Direct messaging between users
- **JSON Protocol**: Clean and extensible communication protocol

## System Requirements

- Python 3.7+
- Required Python packages (install via `pip install -r requirements.txt`):
  - bcrypt
  - socket
  - json
  - threading
  - time
  - os
  - enum
  - random

## Configuration

The application uses a `.env` file for configuration. Key settings include:

```
# Server IP addresses
SERVER1_IP=127.0.0.1  # For local testing
SERVER2_IP=127.0.0.1
SERVER3_IP=127.0.0.1

# For distributed deployment, use actual IP addresses. Below are examples:
# SERVER1_IP=192.168.1.1
# SERVER2_IP=192.168.1.2
# SERVER3_IP=192.168.1.3

# Server ports for replica communication
REPLICA_PORT1=8081
REPLICA_PORT2=8082
REPLICA_PORT3=8083

# Client ports
CLIENT_PORT1=8091
CLIENT_PORT2=8092
CLIENT_PORT3=8093

# Data directories
DATA_DIR=./data
```

## Running the Application

There are two main ways to run the application:

### 1. Single-Machine Deployment (`start_cluster.sh`)

The `start_cluster.sh` script starts all servers on a single machine, which is ideal for testing and development.

```bash
# Make the script executable
chmod +x start_cluster.sh

# Run the cluster
./start_cluster.sh
```

This will:
- Start 3 replica servers on the same machine
- Configure them to communicate with each other
- Make them available for client connections

### 2. Distributed Deployment (`setup_distributed.sh`)

The `setup_distributed.sh` script is designed to run individual servers on separate machines in a distributed environment.

```bash
# Make the script executable
chmod +x setup_distributed.sh

# On Server 1
./setup_distributed.sh 1

# On Server 2
./setup_distributed.sh 2

# On Server 3
./setup_distributed.sh 3
```

For a distributed setup:

1. Edit the `.env` file on each machine to use the correct IP addresses
2. Ensure all machines can communicate over the specified ports
3. Run the appropriate server number on each machine

## Client Usage

To connect to the chat system:

```bash
# Navigate to the client directory
cd client

# Run the client
python client.py
```

The client will automatically attempt to connect to available servers. If the server connected to the client fails, the client will reconnect to another server.

### Client Commands

- **Register**: Create a new user account
- **Login**: Access your account
- **Send Message**: Communicate with other users
- **View Messages**: See messages sent to you
- **Delete Account**: Remove your account and all data

## System Architecture

The system follows a primary-backup replication architecture:

1. **Primary Server**: Handles all write operations and replicates them to backups
2. **Backup Servers**: Forward client requests to the primary and replicate data
3. **Leader Election**: Uses a consensus algorithm to elect a new primary if needed
4. **Client Handling**: Any server can accept client connections

## Troubleshooting

### Common Issues

- **Connection Refused**: Ensure servers are running and ports are open (Give some time for servers to spin up during the first initialization and after a server fails)
- **Authentication Failures**: Check username and password
- **Replication Errors**: Verify network connectivity between servers (Correct ports, IP addresses, address bindings)

### Logs

Server logs provide valuable debugging information:
- Check terminal output for each server
- Look for error messages indicating connection or replication issues
