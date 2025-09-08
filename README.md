The project is to fetch celsius temperature from OpenWeatherMap and visualize it in kibana.
We are doing it using multiple microservices managed by docker compose.

- `weather-sender` publishes JSON weather events to RabbitMQ.
- `logstash` consumes from RabbitMQ and indexes into Elasticsearch (index: `rabbitmq-logs`).
- `kibana` explores the data
- `two post jobs` run one after the other, first create data view and the second imports a dashboard via the Saved Objects API using the "dashboard_source.json".

## Requirements for running
- Docker 

## How to run?
git clone <this-repo-url>
cd weatherboy
docker compose up -d 