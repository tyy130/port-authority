#!/bin/bash
# Example: Using Port Authority from Bash

# Request a port
PORT=$(port-request myproject myservice --pool web)
if [ $? -ne 0 ]; then
    echo "Failed to request port"
    exit 1
fi

echo "Allocated port: $PORT"

# Start your service on that port
echo "Starting service on port $PORT..."
# your-service --port $PORT &
# SERVICE_PID=$!

# When done, release the port
# trap "kill $SERVICE_PID; port-request release myproject myservice" EXIT

# Check status
echo ""
echo "Current allocations:"
port-request status
