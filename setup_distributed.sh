#!/bin/bash

# Get the project root directory (assuming the script is in the project root)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables from .env file if it exists
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE"
    source "$ENV_FILE"
fi

# Set default values if not provided in environment
# IP addresses for the three servers
SERVER1_IP="${SERVER1_IP:-10.250.145.247}"
SERVER2_IP="${SERVER2_IP:-10.250.145.247}"
SERVER3_IP="${SERVER3_IP:-10.250.145.247}"

# Server ports
REPLICA_PORT1="${REPLICA_PORT1:-8081}"
REPLICA_PORT2="${REPLICA_PORT2:-8082}"
REPLICA_PORT3="${REPLICA_PORT3:-8083}"

# Client ports (these are offset by 10 from replica ports)
CLIENT_PORT1="${CLIENT_PORT1:-8091}"
CLIENT_PORT2="${CLIENT_PORT2:-8092}"
CLIENT_PORT3="${CLIENT_PORT3:-8093}"

# Virtual environment path
VENV_PATH="${VENV_PATH:-$PROJECT_DIR/backend/replication_env}"

# Data directories
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
REPLICA1_DIR="${REPLICA1_DIR:-$DATA_DIR/replica1}"
REPLICA2_DIR="${REPLICA2_DIR:-$DATA_DIR/replica2}"
REPLICA3_DIR="${REPLICA3_DIR:-$DATA_DIR/replica3}"

# Python command
PYTHON_CMD="${PYTHON_CMD:-python3}"

# Controller script path
CONTROLLER_SCRIPT="${CONTROLLER_SCRIPT:-$PROJECT_DIR/backend/controller/routes.py}"

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
mkdir -p "$REPLICA1_DIR"
mkdir -p "$REPLICA2_DIR"
mkdir -p "$REPLICA3_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# Start the specified server
case $SERVER_NUM in
    "1")
        echo "Starting Server 1..."
        $PYTHON_CMD "$CONTROLLER_SCRIPT" \
            --id "replica1" \
            --port $REPLICA_PORT1 \
            --host $SERVER1_IP \
            --client-port $CLIENT_PORT1 \
            --data-dir "$REPLICA1_DIR" \
            --replicas "$SERVER2_IP:$REPLICA_PORT2,$SERVER3_IP:$REPLICA_PORT3"
        ;;
    "2")
        echo "Starting Server 2..."
        $PYTHON_CMD "$CONTROLLER_SCRIPT" \
            --id "replica2" \
            --port $REPLICA_PORT2 \
            --host $SERVER2_IP \
            --client-port $CLIENT_PORT2 \
            --data-dir "$REPLICA2_DIR" \
            --replicas "$SERVER1_IP:$REPLICA_PORT1,$SERVER3_IP:$REPLICA_PORT3"
        ;;
    "3")
        echo "Starting Server 3..."
        $PYTHON_CMD "$CONTROLLER_SCRIPT" \
            --id "replica3" \
            --port $REPLICA_PORT3 \
            --host $SERVER3_IP \
            --client-port $CLIENT_PORT3 \
            --data-dir "$REPLICA3_DIR" \
            --replicas "$SERVER1_IP:$REPLICA_PORT1,$SERVER2_IP:$REPLICA_PORT2"
        ;;
esac

# Check if running as root (needed for low port numbers if used)
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. This is not recommended."
fi