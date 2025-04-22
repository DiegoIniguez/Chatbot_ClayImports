#!/bin/bash

echo "🧹 Killing VSCode Server..."
pkill -f vscode
sleep 1
echo "🧹 Removing server folders..."
rm -rf ~/.vscode-server ~/.vscode-remote
echo "✅ VSCode Server cleaned. You are safe now."
