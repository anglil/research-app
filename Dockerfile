# Use official lightweight Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2 (Postgres driver)
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit default port (Cloud Run expects 8080 usually)
EXPOSE 8080

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
