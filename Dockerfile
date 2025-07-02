# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements/web.txt requirements/
RUN pip install --no-cache-dir -r requirements/web.txt

# Copy the entire application
COPY . .

# Create necessary directories (in case they don't exist)
RUN mkdir -p data/uploads data/analyses logs static/css static/js

# Expose the port that Railway will use
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "run_web.py"]