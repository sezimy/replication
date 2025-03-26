#!/bin/bash

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

# Function to determine which server to start based on local IP
start_server() {
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    echo "Local IP: $LOCAL_IP"

    case $LOCAL_IP in
        $SERVER1_IP)
            echo "Starting Server 1..."
            python3 backend/main.py \
                --port $REPLICA_PORT1 \
                --host $SERVER1_IP \
                --replica-ports "$SERVER2_IP:$REPLICA_PORT2,$SERVER3_IP:$REPLICA_PORT3" \
                --client-port $CLIENT_PORT1
            ;;
        $SERVER2_IP)
            echo "Starting Server 2..."
            python3 backend/main.py \
                --port $REPLICA_PORT2 \
                --host $SERVER2_IP \
                --replica-ports "$SERVER1_IP:$REPLICA_PORT1,$SERVER3_IP:$REPLICA_PORT3" \
                --client-port $CLIENT_PORT2
            ;;
        $SERVER3_IP)
            echo "Starting Server 3..."
            python3 backend/main.py \
                --port $REPLICA_PORT3 \
                --host $SERVER3_IP \
                --replica-ports "$SERVER1_IP:$REPLICA_PORT1,$SERVER2_IP:$REPLICA_PORT2" \
                --client-port $CLIENT_PORT3
            ;;
        *)
            echo "Error: Local IP ($LOCAL_IP) doesn't match any configured server IP"
            echo "Please check the IP configuration in the script"
            exit 1
            ;;
    esac
}

# Check if running as root (needed for low port numbers if used)
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. This is not recommended."
fi

# Create necessary directories if they don't exist
mkdir -p data/replica1
mkdir -p data/replica2
mkdir -p data/replica3

# Start the appropriate server
start_server 