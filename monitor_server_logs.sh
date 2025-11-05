#!/bin/bash
# Monitor server logs for performance timing
echo "Monitoring server logs for performance timing..."
echo "Upload a document and watch for timing messages..."
echo "=" | head -c 70 && echo
echo ""

# Try to find and tail server logs
# If server is running in terminal, you'll see output there
# This script helps identify where logs are

echo "Looking for server process..."
ps aux | grep -E "uvicorn|python.*main" | grep -v grep

echo ""
echo "To see timing logs, check the terminal where uvicorn is running"
echo "Look for messages like:"
echo "  - 'Document preprocessed in X.XXs'"
echo "  - 'Task creation took X.XXs'"
echo "  - 'CrewAI execution took X.XXs'"
echo "  - 'Summarization completed in X.XXs'"
echo "  - 'DOCX text extraction completed in X.XXs'"

