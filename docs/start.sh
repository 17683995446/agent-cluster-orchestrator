#!/bin/bash
# Quick start script for architecture documentation server
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Architecture Documentation Server"
echo "========================================="
echo ""
echo "Starting server on http://localhost:8080/architecture.html"
echo "Press Ctrl+C to stop the server"
echo ""

python3 -m http.server 8080
