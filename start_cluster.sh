#!/bin/bash

# This script starts a cluster of 3 replica servers for 2-fault tolerance
# Usage: ./start_cluster.sh

# Get the project root directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables from .env file if it exists
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE"
    source "$ENV_FILE"
fi

# Set default values if not provided in environment
# Server ports
REPLICA_PORT1="${REPLICA_PORT1:-8081}"
REPLICA_PORT2="${REPLICA_PORT2:-8082}"
REPLICA_PORT3="${REPLICA_PORT3:-8083}"

# Client ports
CLIENT_PORT1="${CLIENT_PORT1:-8091}"
CLIENT_PORT2="${CLIENT_PORT2:-8092}"
CLIENT_PORT3="${CLIENT_PORT3:-8093}"

# Data directories
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data}"
REPLICA1_DIR="${REPLICA1_DIR:-$DATA_DIR/replica1}"
REPLICA2_DIR="${REPLICA2_DIR:-$DATA_DIR/replica2}"
REPLICA3_DIR="${REPLICA3_DIR:-$DATA_DIR/replica3}"

# Kill any existing server processes more thoroughly
echo "Stopping any existing server processes..."
pkill -f "python backend/controller/routes.py" || true

# Kill any processes using our ports
for PORT in $REPLICA_PORT1 $REPLICA_PORT2 $REPLICA_PORT3 $CLIENT_PORT1 $CLIENT_PORT2 $CLIENT_PORT3; do
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
done

# Close any existing terminal windows running our servers
osascript -e 'tell application "Terminal" to close (every window whose name contains "'$REPLICA_PORT1'" or name contains "'$REPLICA_PORT2'" or name contains "'$REPLICA_PORT3'")' || true
sleep 3  # Give processes more time to fully terminate

# Define replica information
REPLICA_LIST="localhost:$REPLICA_PORT1,localhost:$REPLICA_PORT2,localhost:$REPLICA_PORT3"

# Make scripts executable
chmod +x start_replica.sh

# Create data directories if they don't exist
mkdir -p $REPLICA1_DIR $REPLICA2_DIR $REPLICA3_DIR

# Start each replica in a separate terminal window with separate client ports
# Replica 1
echo "Starting Replica 1 on replication port $REPLICA_PORT1 and client port $CLIENT_PORT1"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica1 $REPLICA_PORT1 $REPLICA1_DIR $REPLICA_LIST $CLIENT_PORT1\""
sleep 2  # Give the first replica time to start up

# Replica 2
echo "Starting Replica 2 on replication port $REPLICA_PORT2 and client port $CLIENT_PORT2"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica2 $REPLICA_PORT2 $REPLICA2_DIR $REPLICA_LIST $CLIENT_PORT2\""
sleep 2  # Give the second replica time to start up

# Replica 3
echo "Starting Replica 3 on replication port $REPLICA_PORT3 and client port $CLIENT_PORT3"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica3 $REPLICA_PORT3 $REPLICA3_DIR $REPLICA_LIST $CLIENT_PORT3\""

echo "Started 3 replicas. The system is now 2-fault tolerant."
echo "You can connect to any of the replicas using the client on ports $CLIENT_PORT1, $CLIENT_PORT2, or $CLIENT_PORT3."
