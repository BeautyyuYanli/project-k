#!/bin/bash
FILE="$HOME/restarting"
if [ ! -f "$FILE" ]; then
    touch "$FILE"
    # Find and kill the process running start.sh
    # Using pgrep/pkill with full path to be specific
    pkill -f "bash $HOME/start.sh" || pkill -f "$HOME/start.sh"
    echo "Restarting initiated."
else
    rm "$FILE"
    echo "already restarted"
fi
