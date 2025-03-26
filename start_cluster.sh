#!/bin/bash

# This script starts a cluster of 3 replica servers for 2-fault tolerance
# Usage: ./start_cluster.sh

# Kill any existing server processes more thoroughly
echo "Stopping any existing server processes..."
pkill -f "python backend/controller/routes.py" || true
# Kill any processes using our ports
for PORT in 8081 8082 8083 8091 8092 8093; do
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
done
# Close any existing terminal windows running our servers
osascript -e 'tell application "Terminal" to close (every window whose name contains "8081" or name contains "8082" or name contains "8083")' || true
sleep 3  # Give processes more time to fully terminate

# Define replica information
REPLICA_LIST="localhost:8081,localhost:8082,localhost:8083"

# Make scripts executable
chmod +x start_replica.sh

# Start each replica in a separate terminal window with separate client ports
# Replica 1 - Replication port 8081, Client port 8091
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica1 8081 ./data/replica1 $REPLICA_LIST 8091\""
sleep 2  # Give the first replica time to start up

# Replica 2 - Replication port 8082, Client port 8092
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica2 8082 ./data/replica2 $REPLICA_LIST 8092\""
sleep 2  # Give the second replica time to start up

# Replica 3 - Replication port 8083, Client port 8093
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && ./start_replica.sh replica3 8083 ./data/replica3 $REPLICA_LIST 8093\""

echo "Started 3 replicas. The system is now 2-fault tolerant."
echo "You can connect to any of the replicas using the client on ports 8091, 8092, or 8093."
