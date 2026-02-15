FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for matplotlib/pandas sometimes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port for Mini App
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "app.main"]
