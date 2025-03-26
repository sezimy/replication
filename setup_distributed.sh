#!/bin/bash

# Get the project root directory (assuming the script is in the project root)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# IP addresses for the three servers
SERVER1_IP="10.250.103.230"  # Replace with actual IP
SERVER2_IP="10.250.103.230"  # Replace with actual IP
SERVER3_IP="10.250.145.247"  # Replace with actual IP

# Server ports
REPLICA_PORT1="8081"
REPLICA_PORT2="8082"
REPLICA_PORT3="8083"

# Client ports (these are offset by 10 from replica ports)
CLIENT_PORT1="8091"
CLIENT_PORT2="8092"
CLIENT_PORT3="8093"

# Check if server number argument is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <server-number>"
    echo "Example: $0 1  # to start server 1"
    exit 1
fi

SERVER_NUM=$1

# Validate server number
if [ "$SERVER_NUM" != "1" ] && [ "$SERVER_NUM" != "2" ] && [ "$SERVER_NUM" != "3" ]; then
    echo "Error: Server number must be 1, 2, or 3"
    exit 1
fi

# Create necessary directories if they don't exist
mkdir -p "$PROJECT_DIR/data/replica1"
mkdir -p "$PROJECT_DIR/data/replica2"
mkdir -p "$PROJECT_DIR/data/replica3"

# Activate virtual environment
echo "Activating virtual environment..."
source "$PROJECT_DIR/backend/replication_env/bin/activate"

# Start the specified server
case $SERVER_NUM in
    "1")
        echo "Starting Server 1..."
        python3 "$PROJECT_DIR/backend/controller/routes.py" \
            --id "replica1" \
            --port $REPLICA_PORT1 \
            --host $SERVER1_IP \
            --client-port $CLIENT_PORT1 \
            --data-dir "$PROJECT_DIR/data/replica1" \
            --replicas "$SERVER2_IP:$REPLICA_PORT2,$SERVER3_IP:$REPLICA_PORT3"
        ;;
    "2")
        echo "Starting Server 2..."
        python3 "$PROJECT_DIR/backend/controller/routes.py" \
            --id "replica2" \
            --port $REPLICA_PORT2 \
            --host $SERVER2_IP \
            --client-port $CLIENT_PORT2 \
            --data-dir "$PROJECT_DIR/data/replica2" \
            --replicas "$SERVER1_IP:$REPLICA_PORT1,$SERVER3_IP:$REPLICA_PORT3"
        ;;
    "3")
        echo "Starting Server 3..."
        python3 "$PROJECT_DIR/backend/controller/routes.py" \
            --id "replica3" \
            --port $REPLICA_PORT3 \
            --host $SERVER3_IP \
            --client-port $CLIENT_PORT3 \
            --data-dir "$PROJECT_DIR/data/replica3" \
            --replicas "$SERVER1_IP:$REPLICA_PORT1,$SERVER2_IP:$REPLICA_PORT2"
        ;;
esac

# Check if running as root (needed for low port numbers if used)
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. This is not recommended."
fi 