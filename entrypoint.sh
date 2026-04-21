#!/bin/sh
# entrypoint.sh
# Starts the Taggarr scan daemon (main.py) and the UI server (server.py)
# in parallel. If UI_ENABLED=false, only main.py is started.

set -e

UI_ENABLED="${UI_ENABLED:-true}"

if [ "$UI_ENABLED" = "true" ]; then
    echo "🌐 Starting Taggarr UI server..."
    python server.py &
fi

echo "🏷️  Starting Taggarr scan daemon..."
exec python main.py "$@"
