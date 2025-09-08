import requests
import pika
import json
import time
import os

# === CONFIG ===
RABBIT_HOST = "rabbitmq"
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
CITY = "Hanoi"
QUEUE_NAME = "my-queue" 
INTERVAL = 3600  # 1 hour in seconds

def get_weather():
    """Fetch current weather for Hanoi from OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    return {
        "city": data.get("name"),
        "temperature_celsius": data.get("main", {}).get("temp")
    }

def send_to_rabbitmq(message):
    """Send message to RabbitMQ queue."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  # make message persistent
    )
    connection.close()

if __name__ == "__main__":
    while True:
        try:
            weather = get_weather()
            print(f"[INFO] Sending weather data for {CITY} to RabbitMQ: {weather}")
            send_to_rabbitmq(weather)
        except Exception as e:
            print(f"[ERROR] {e}")
        
        print(f"waiting for {INTERVAL} seconds")
        time.sleep(INTERVAL)
