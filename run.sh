#!/bin/bash
# Navigate to the script's directory
cd "$(dirname "$0")"

# Activate the virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: .venv directory not found. Please create a virtual environment first."
    exit 1
fi

# Build the frontend if not already compiled
if [ ! -d "frontend/dist" ]; then
    echo "Compiling Vite frontend..."
    cd frontend && npm run build && cd ..
fi

# Run the FastAPI server (which serves both the API and the static frontend)
echo "Starting LeadScout AI on http://127.0.0.1:8000..."
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
