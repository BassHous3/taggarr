#!/bin/bash
# entrypoint.sh — starts Flask UI and taggarr scanner in the same container

set -e

echo "🏷️  Starting Taggarr..."

# Start Flask UI in the background
echo "🌐 Starting web UI on port ${WEB_PORT:-5000}..."
python3 /app/web/server.py &
FLASK_PID=$!

# Start taggarr scanner (blocks, runs the loop)
echo "🔍 Starting scanner..."
python3 /app/main.py "$@"

# If scanner exits, kill Flask too
kill $FLASK_PID 2>/dev/null
