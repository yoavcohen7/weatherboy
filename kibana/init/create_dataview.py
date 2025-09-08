import os, time, json, sys
import requests

KIBANA_URL = os.getenv("KIBANA_URL", "http://kibana:5601")
ELASTIC_URL = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")

DATA_VIEW_TITLE = os.getenv("DATA_VIEW_TITLE", "rabbitmq-logs*")
DATA_VIEW_NAME = os.getenv("DATA_VIEW_NAME", "RabbitMQ Logs")
DATA_VIEW_TIMEFIELD = os.getenv("DATA_VIEW_TIMEFIELD", "@timestamp")
REQUIRED_INDEX = os.getenv("REQUIRED_INDEX", DATA_VIEW_TITLE)

HEADERS = {
    "Content-Type": "application/json",
    "kbn-xsrf": "true",
}

AUTH = None
if os.getenv("KIBANA_USERNAME") and os.getenv("KIBANA_PASSWORD"):
    AUTH = (os.getenv("KIBANA_USERNAME"), os.getenv("KIBANA_PASSWORD"))

def wait_for(url, ok=lambda r: r.ok, desc="endpoint", timeout=600, sleep=5, **kwargs):
    print(f"Waiting for {desc} at {url} ...")
    start = time.time()
    while True:
        try:
            r = requests.get(url, timeout=10, **kwargs)
            if ok(r):
                print(f"{desc} is ready.")
                return r
            else:
                print(f"{desc} not ready yet: {r.status_code} {r.text[:120]}")
        except Exception as e:
            print(f"{desc} not reachable yet: {e}")
        if time.time() - start > timeout:
            print(f"Timeout waiting for {desc}.")
            sys.exit(1)
        time.sleep(sleep)

def index_exists(pattern: str) -> bool:
    # Use cat indices to see if any index matches
    try:
        r = requests.get(f"{ELASTIC_URL}/_cat/indices/{pattern}?format=json", timeout=10)
        if r.ok and len(r.json()) > 0:
            return True
        # Fallback: try a search and see if hits exist
        r = requests.get(f"{ELASTIC_URL}/{pattern}/_search?size=0", timeout=10)
        if r.ok:
            j = r.json()
            # If the index isn't there, ES may return an error; ok guards it.
            total = j.get("hits", {}).get("total", {}).get("value", 0)
            return total >= 0  # zero docs still fine; index exists
    except Exception as e:
        print(f"index_exists check error: {e}")
    return False

def create_data_view():
    """
    Creates a Kibana data view using predefined constants.

    Sends a POST request to the Kibana API to create a data view. If the data view already exists,
    the function treats it as a successful, idempotent operation. Prints the result and returns True
    on success, False otherwise.
    """
    payload = {
        "data_view": {
            "title": DATA_VIEW_TITLE,
            "name": DATA_VIEW_NAME,
            "timeFieldName": DATA_VIEW_TIMEFIELD
        }
    }
    url = f"{KIBANA_URL}/api/data_views/data_view"
    r = requests.post(url, headers=HEADERS, data=json.dumps(payload), auth=AUTH, timeout=15)
    if r.status_code in (200, 201):
        print("Data View created:", r.json().get("data_view", {}).get("id"))
        return True
    else:
        # If it already exists, Kibana returns 409 or 400 with a message; treat as success-idempotent.
        body = r.text
        if r.status_code in (400, 409) and ("exists" in body or "Duplicate" in body or "data view exists" in body):
            print("Data View already exists. Skipping.")
            return True
        print("Failed to create Data View:", r.status_code, body[:300])
        return False

if __name__ == "__main__":
    # 1) Wait for Kibana status (healthcheck already ensures this, but extra-safe)
    wait_for(f"{KIBANA_URL}/api/status", desc="Kibana", auth=AUTH)

    # 2) Wait until the index (or pattern) is available in ES
    print(f"Waiting for Elasticsearch index/pattern '{REQUIRED_INDEX}' ...")
    start = time.time()
    while not index_exists(REQUIRED_INDEX):
        if time.time() - start > 600:
            print(f"Timeout waiting for index/pattern '{REQUIRED_INDEX}'.")
            sys.exit(1)
        time.sleep(5)
    print(f"Index/pattern '{REQUIRED_INDEX}' detected.")

    # 3) Create Data View 
    ok = create_data_view()
    sys.exit(0 if ok else 1)
