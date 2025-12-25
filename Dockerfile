FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY taskrouter_mcp.py .

# Run the server
CMD ["python", "taskrouter_mcp.py"]
