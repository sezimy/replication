#!/bin/bash

# This script starts a replica server with the specified ID, port, and data directory
# Usage: ./start_replica.sh <id> <port> <data_dir> <replica_list> [client_port]

if [ $# -lt 4 ]; then
    echo "Usage: ./start_replica.sh <id> <port> <data_dir> <replica_list> [client_port]"
    echo "Example: ./start_replica.sh replica1 8081 ./data/replica1 localhost:8081,localhost:8082,localhost:8083 8091"
    exit 1
fi

SERVER_ID=$1
PORT=$2
DATA_DIR=$3
REPLICAS=$4
CLIENT_PORT=${5:-$PORT}  # Use client_port if provided, otherwise use the same port

# More thorough check and cleanup for port usage
echo "Checking if ports $PORT and $CLIENT_PORT are available..."

# Kill any process using the replication port
if lsof -i:$PORT > /dev/null 2>&1; then
    echo "Port $PORT is already in use. Killing the process..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2  # Give the process time to terminate
fi

# Kill any process using the client port if different
if [ "$PORT" != "$CLIENT_PORT" ] && lsof -i:$CLIENT_PORT > /dev/null 2>&1; then
    echo "Client port $CLIENT_PORT is already in use. Killing the process..."
    lsof -ti:$CLIENT_PORT | xargs kill -9 2>/dev/null || true
    sleep 2  # Give the process time to terminate
fi

# Create data directory if it doesn't exist
mkdir -p $DATA_DIR

# Start the server with separate client port if specified
if [ "$PORT" != "$CLIENT_PORT" ]; then
    echo "Starting server $SERVER_ID with replication port $PORT and client port $CLIENT_PORT"
    python backend/controller/routes.py --id $SERVER_ID --port $PORT --client-port $CLIENT_PORT --data-dir $DATA_DIR --replicas $REPLICAS
else
    echo "Starting server $SERVER_ID with port $PORT"
    python backend/controller/routes.py --id $SERVER_ID --port $PORT --data-dir $DATA_DIR --replicas $REPLICAS
fi
