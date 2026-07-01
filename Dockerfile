FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages (like sqlite3, chroma, etc)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the API port
EXPOSE 8000

# Set environment variables for production
ENV HOST=0.0.0.0
ENV PORT=8000

# Command to run the application (assuming server.py uses uvicorn or similar)
CMD ["python", "server.py"]
