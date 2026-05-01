#!/bin/bash
# Force Python 3.11 if multiple versions exist
export PATH="/opt/render/project/.venv/bin:$PATH"

# Start the server
cd /opt/render/project/src
uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}