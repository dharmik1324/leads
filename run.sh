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

# Run the Streamlit application (serves both frontend and backend)
echo "Starting LeadScout AI (Frontend & Backend)..."
streamlit run app.py
