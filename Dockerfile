FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for build tools)
# RUN apt-get update && apt-get install -y build-essential

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Expose the configured port
EXPOSE 8504

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8504", "--server.address=0.0.0.0"]
