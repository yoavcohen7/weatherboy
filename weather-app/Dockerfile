FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements 
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script
COPY weather_to_rabbitmq.py .

# Run the script
CMD ["python", "weather_to_rabbitmq.py"]
