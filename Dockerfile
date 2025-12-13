FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# - LibreOffice for PPT/PPTX to PDF conversion
# - Fonts for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data and logs directories
RUN mkdir -p /app/data /app/logs

# Expose the configured port
EXPOSE 3333

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3333"]
