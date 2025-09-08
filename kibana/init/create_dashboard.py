# # kibana/init/create_dashboard.py
# # Creates/updates a Kibana Dashboard that embeds a BY-VALUE Lens panel (no saved Lens object).
# # NO SPACES (Default space only). Clears stale top-level references.
# #
# # Env:
# #   KIBANA_URL               (e.g., http://kibana:5601)
# #   DATA_VIEW_TITLE          (display name OR pattern, e.g., "RabbitMQ Logs" OR "rabbitmq-logs*")
# #   DASHBOARD_TITLE          (e.g., "Weather Dashboard")
# #   LENS_TITLE               (e.g., "Temperature (last value)")
# #   LENS_FIELD               (e.g., "temperature_celsius")
# #   TIMESTAMP_FIELD          (e.g., "@timestamp")
# #   KIBANA_USERNAME          (optional, if security enabled)
# #   KIBANA_PASSWORD          (optional, if security enabled)
# #   DEBUG=1                  (optional; logs payloads and responses)
# #
# # Usage (host):
# #   KIBANA_URL=http://localhost:5601 DATA_VIEW_TITLE='rabbitmq-logs*' \
# #   DASHBOARD_TITLE='Weather Dashboard' LENS_TITLE='Temperature (last value)' \
# #   LENS_FIELD='temperature_celsius' TIMESTAMP_FIELD='@timestamp' DEBUG=1 \
# #   python kibana/init/create_dashboard.py

# import os, sys, json, time, traceback
# import requests

# # ---------------- Logging helpers ----------------
# def log(msg: str) -> None:
#     print(msg, flush=True)

# def j(obj) -> str:
#     try:
#         return json.dumps(obj, ensure_ascii=False)
#     except Exception:
#         return str(obj)

# MAX_LOG = 1400

# def log_json(prefix: str, obj) -> None:
#     s = j(obj)
#     if len(s) > MAX_LOG:
#         s = s[:MAX_LOG] + "...(truncated)"
#     log(prefix + s)

# # ---------------- Env ----------------
# KIBANA_URL      = os.getenv("KIBANA_URL", "http://kibana:5601").rstrip("/")
# DATA_VIEW_QUERY = os.getenv("DATA_VIEW_TITLE", "RabbitMQ Logs")
# DASHBOARD_TITLE = os.getenv("DASHBOARD_TITLE", "Weather Dashboard")
# LENS_TITLE      = os.getenv("LENS_TITLE", "Temperature (last value)")
# TIMESTAMP_FIELD = os.getenv("TIMESTAMP_FIELD", "@timestamp")
# LENS_FIELD      = os.getenv("LENS_FIELD", "temperature_celsius")
# DEBUG           = os.getenv("DEBUG", "").lower() in ("1","true","yes","y")

# AUTH = None
# if os.getenv("KIBANA_USERNAME") and os.getenv("KIBANA_PASSWORD"):
#     AUTH = (os.getenv("KIBANA_USERNAME"), os.getenv("KIBANA_PASSWORD"))

# HEADERS = {
#     "Content-Type": "application/json",
#     "Accept": "application/json",
#     "kbn-xsrf": "true"
# }

# log("=== ENV (Default space only) ===")
# log(f"KIBANA_URL={KIBANA_URL}")
# log(f"DATA_VIEW_TITLE={DATA_VIEW_QUERY}")
# log(f"DASHBOARD_TITLE={DASHBOARD_TITLE}")
# log(f"LENS_TITLE={LENS_TITLE}")
# log(f"TIMESTAMP_FIELD={TIMESTAMP_FIELD}")
# log(f"LENS_FIELD={LENS_FIELD}")
# log(f"AUTH={'enabled' if AUTH else 'disabled'}")
# log(f"DEBUG={'on' if DEBUG else 'off'}")

# # ---------------- HTTP wrapper ----------------
# def http(method: str, path: str, desc: str, **kw) -> requests.Response:
#     url = f"{KIBANA_URL}{path}"
#     log(f"\n[HTTP] {method} {url} -- {desc}")
#     body = kw.get("data") if "data" in kw else kw.get("json")
#     if DEBUG and body is not None:
#         if isinstance(body, (dict, list)):
#             log_json("        payload(json): ", body)
#         else:
#             s = str(body)
#             if len(s) > MAX_LOG: s = s[:MAX_LOG] + "...(truncated)"
#             log("        payload: " + s)
#     t0 = time.time()
#     r = requests.request(method, url, headers=HEADERS, auth=AUTH, timeout=60, **kw)
#     dt = (time.time() - t0) * 1000
#     log(f"[HTTP] -> {r.status_code} in {dt:.1f} ms")
#     if DEBUG:
#         try:
#             log_json("        response: ", r.json())
#         except Exception:
#             s = r.text or ""
#             if len(s) > MAX_LOG: s = s[:MAX_LOG] + "...(truncated)"
#             log("        response(text): " + s)
#     r.raise_for_status()
#     return r

# # ---------------- Data view helpers ----------------
# def list_data_views():
#     log("\n[STEP] Listing Data Views (Default space) ...")
#     r = http("GET", "/api/saved_objects/_find?type=index-pattern&per_page=10000", "list data views")
#     items = r.json().get("saved_objects", [])
#     log(f"[INFO] Found {len(items)} data view(s)")
#     for so in items:
#         a = so.get("attributes", {})
#         log(f"  id={so.get('id')}  name='{a.get('name')}'  title='{a.get('title')}'")
#     return items

# def resolve_dataview_id() -> str:
#     log("\n[STEP] Resolving Data View by name/pattern ...")
#     log(f"Looking for DATA_VIEW_TITLE='{DATA_VIEW_QUERY}'")
#     items = list_data_views()
#     # Exact match on display name or pattern
#     for so in items:
#         a = so.get("attributes", {})
#         if a.get("name") == DATA_VIEW_QUERY or a.get("title") == DATA_VIEW_QUERY:
#             log(f"[MATCH] exact: id={so['id']}")
#             return so["id"]
#     # Contains fallback (case-insensitive)
#     q = DATA_VIEW_QUERY.lower()
#     for so in items:
#         a = so.get("attributes", {})
#         hay = f"{a.get('name','')} {a.get('title','')}".lower()
#         if q in hay:
#             log(f"[MATCH] contains: id={so['id']} name='{a.get('name')}' title='{a.get('title')}'")
#             return so["id"]
#     log("[WARN] No matching data view")
#     return None

# # ---------------- Dashboard helpers ----------------
# def find_dashboard_id(title: str) -> str:
#     log("\n[STEP] Checking if dashboard exists ...")
#     r = http("GET", f"/api/saved_objects/_find?type=dashboard&search_fields=title&search={title}&per_page=10000",
#              "find dashboard by title")
#     for so in r.json().get("saved_objects", []):
#         if so.get("attributes", {}).get("title") == title:
#             log(f"[INFO] Dashboard exists: id={so['id']}")
#             return so["id"]
#     log("[INFO] Dashboard not found; will create.")
#     return None

# def build_lens_attrs_by_value(dv_id: str) -> dict:
#     log("\n[STEP] Building by-value Lens attributes ...")
#     log(f"  dv_id={dv_id}, LENS_TITLE={LENS_TITLE}, X={TIMESTAMP_FIELD}, Y={LENS_FIELD}")
#     layer_id = "layer-1"
#     state = {
#         "query": {"language": "kuery", "query": ""},
#         "filters": [],
#         "datasourceStates": {
#             "formBased": {
#                 "layers": {
#                     layer_id: {
#                         "indexPatternId": dv_id,  # critical link to data view
#                         "columns": {
#                             "x": {
#                                 "label": TIMESTAMP_FIELD,
#                                 "dataType": "date",
#                                 "operationType": "date_histogram",
#                                 "sourceField": TIMESTAMP_FIELD,
#                                 "isBucketed": True,
#                                 "params": {"interval": "auto"}
#                             },
#                             "y": {
#                                 "label": f"Last value of {LENS_FIELD}",
#                                 "dataType": "number",
#                                 "operationType": "last_value",
#                                 "sourceField": LENS_FIELD,
#                                 "isBucketed": False,
#                                 "params": {"sortField": TIMESTAMP_FIELD, "showArrayValues": False}
#                             }
#                         },
#                         "columnOrder": ["x", "y"],
#                         "incompleteColumns": {},
#                         "sampling": 1
#                     }
#                 }
#             }
#         },
#         "visualization": {
#             "legend": {"isVisible": True, "position": "right"},
#             "preferredSeriesType": "line",
#             "layers": [{
#                 "layerId": layer_id,
#                 "accessors": ["y"],
#                 "position": "top",
#                 "seriesType": "line",
#                 "xAccessor": "x",
#                 "yConfig": [],
#                 "layerType": "data"
#             }]
#         },
#         "adHocDataViews": {}
#     }
#     attrs = {
#         "title": LENS_TITLE,
#         "description": "By-value Lens via REST API",
#         "visualizationType": "lnsXY",
#         "state": state,
#         "references": [
#             {"type": "index-pattern", "id": dv_id, "name": f"indexpattern-datasource-layer-{layer_id}"}
#         ]
#     }
#     if DEBUG: log_json("Lens attrs: ", attrs)
#     return attrs

# def upsert_dashboard_by_value(lens_attrs: dict) -> str:
#     log("\n[STEP] Upserting dashboard (by-value panel) ...")
#     panel_uid = "panel_0"
#     panel = {
#         "version": "8.15.0",
#         "type": "lens",
#         "embeddableConfig": {"attributes": lens_attrs, "hidePanelTitles": False},
#         "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": panel_uid},
#         "panelIndex": panel_uid
#         # NOTE: no panelRefName for by-value panels
#     }
#     dash_attrs = {
#         "title": DASHBOARD_TITLE,
#         "description": "Dashboard with by-value Lens",
#         "panelsJSON": json.dumps([panel]),
#         "optionsJSON": json.dumps({"hidePanelTitles": False}),
#         "timeRestore": False
#     }
#     payload = {"attributes": dash_attrs, "references": []}  # clear stale refs

#     dash_id = find_dashboard_id(DASHBOARD_TITLE)
#     if dash_id:
#         log(f"[STEP] Updating dashboard id={dash_id} (and clearing references) ...")
#         http("PUT", f"/api/saved_objects/dashboard/{dash_id}", "update dashboard", data=json.dumps(payload))
#         return dash_id
#     else:
#         log("[STEP] Creating dashboard (with empty top-level references) ...")
#         r = http("POST", "/api/saved_objects/dashboard", "create dashboard", data=json.dumps(payload))
#         new_id = r.json().get("id")
#         log(f"[INFO] Created dashboard id={new_id}")
#         return new_id

# def validate_dashboard(dash_id: str) -> bool:
#     log("\n[STEP] Validating saved dashboard ...")
#     so = http("GET", f"/api/saved_objects/dashboard/{dash_id}", "get dashboard SO").json()

#     # Check top-level references are empty (by-value should not need Lens refs)
#     refs = so.get("references", [])
#     log(f"[VERIFY] top-level references: {refs}")
#     if refs:
#         log("[WARN] references not empty; attempting to clear and re-validate ...")
#         # Try to clear again (some versions require a second write)
#         attrs = so.get("attributes", {})
#         http("PUT", f"/api/saved_objects/dashboard/{dash_id}",
#              "clear stale references",
#              data=json.dumps({"attributes": attrs, "references": []}))
#         so = http("GET", f"/api/saved_objects/dashboard/{dash_id}", "re-get dashboard SO").json()
#         refs = so.get("references", [])
#         log(f"[VERIFY] references after clear: {refs}")

#     attrs = so.get("attributes", {})
#     try:
#         panels = json.loads(attrs.get("panelsJSON", "[]"))
#     except Exception:
#         log("[ERROR] panelsJSON not parseable JSON.")
#         return False

#     log(f"[INFO] panels count: {len(panels)}")
#     if DEBUG: log_json("[DEBUG] panelsJSON: ", panels)
#     if not panels:
#         log("[ERROR] No panels found.")
#         return False

#     emb = panels[0].get("embeddableConfig", {})
#     lens_attrs = emb.get("attributes", {})
#     try:
#         dv_id = lens_attrs["state"]["datasourceStates"]["formBased"]["layers"]["layer-1"]["indexPatternId"]
#         log(f"[INFO] Lens by-value layer indexPatternId: {dv_id}")
#     except Exception:
#         log("[ERROR] Lens state missing indexPatternId.")
#         return False

#     # Optional: quick sanity on columns
#     try:
#         x = lens_attrs["state"]["datasourceStates"]["formBased"]["layers"]["layer-1"]["columns"]["x"]
#         y = lens_attrs["state"]["datasourceStates"]["formBased"]["layers"]["layer-1"]["columns"]["y"]
#         log(f"[INFO] X column: op={x.get('operationType')} field={x.get('sourceField')}")
#         log(f"[INFO] Y column: op={y.get('operationType')} field={y.get('sourceField')}")
#     except Exception:
#         log("[WARN] Could not read X/Y columns for validation.")

#     return True

# # ---------------- Main ----------------
# if __name__ == "__main__":
#     try:
#         dv_id = resolve_dataview_id()
#         if not dv_id:
#             existing = [{"id": so["id"],
#                          "name": so.get("attributes", {}).get("name"),
#                          "title": so.get("attributes", {}).get("title")} for so in list_data_views()]
#             log_json("[FATAL] Data View not found. Existing in Default space: ", existing)
#             sys.exit(1)

#         lens_attrs = build_lens_attrs_by_value(dv_id)
#         dash_id = upsert_dashboard_by_value(lens_attrs)
#         ok = validate_dashboard(dash_id)

#         url = f"{KIBANA_URL}/app/dashboards#/view/{dash_id}"
#         log("\n=== DONE (Default space) ===")
#         log(f"Dashboard ID={dash_id}")
#         log(f"Open: {url}")
#         sys.exit(0 if ok else 2)

#     except requests.HTTPError as e:
#         log("[FATAL][HTTP] " + str(e))
#         if e.response is not None:
#             txt = e.response.text or ""
#             if len(txt) > MAX_LOG: txt = txt[:MAX_LOG] + "...(truncated)"
#             log("        response: " + txt)
#         sys.exit(1)
#     except Exception as e:
#         log("[FATAL] " + str(e))
#         log(traceback.format_exc())
#         sys.exit(1)


#!/usr/bin/env python3
"""
Create/Update a Kibana dashboard (Default space, no Spaces).
- Ensures Data View: title= rabbitmq-logs* , name= RabbitMQ Logs , timeField= @timestamp
- Adds a by-value Lens panel: last value of temperature_celsius vs @timestamp
Requires Kibana 8.x with security off (or set KIBANA_USERNAME/PASSWORD).
"""

import os, sys, json, time
import requests

# -------- Config (tweak via envs if needed) --------
KIBANA_URL       = os.getenv("KIBANA_URL", "http://localhost:5601").rstrip("/")
INDEX_PATTERN    = os.getenv("INDEX_PATTERN", "rabbitmq-logs*")      # attributes.title
DATA_VIEW_NAME   = os.getenv("DATA_VIEW_NAME", "RabbitMQ Logs")      # attributes.name (UI display)
TIME_FIELD       = os.getenv("TIME_FIELD", "@timestamp")
TEMP_FIELD       = os.getenv("TEMP_FIELD", "temperature_celsius")
DASHBOARD_TITLE  = os.getenv("DASHBOARD_TITLE", "Weather Dashboard")
LENS_TITLE       = os.getenv("LENS_TITLE", "Temperature (last value)")
DEBUG            = os.getenv("DEBUG", "").lower() in ("1", "true", "yes", "y")

AUTH=None
if os.getenv("KIBANA_USERNAME") and os.getenv("KIBANA_PASSWORD"):
    AUTH=(os.getenv("KIBANA_USERNAME"), os.getenv("KIBANA_PASSWORD"))

HDR = {"kbn-xsrf":"true","Content-Type":"application/json","Accept":"application/json"}

def log(msg): print(msg, flush=True)
def j(obj):   return json.dumps(obj, ensure_ascii=False)

# -------- HTTP helper --------
def http(method, path, desc, **kw):
    url = f"{KIBANA_URL}{path}"
    if DEBUG:
        log(f"[HTTP] {method} {url} -- {desc}")
        if "data" in kw and kw["data"] is not None:
            s = kw["data"] if isinstance(kw["data"], str) else j(kw["data"])
            log(f"        payload: {s[:1400]}{'...(trunc)' if len(s)>1400 else ''}")
    r = requests.request(method, url, headers=HDR, auth=AUTH, timeout=60, **kw)
    if DEBUG:
        try: log("        resp: " + j(r.json()))
        except: log("        resp(text): " + (r.text[:1400] if r.text else ""))
    r.raise_for_status()
    return r

# -------- Wait until Kibana is actually ready (optional but useful) --------
def wait_kibana(timeout=600):
    log("[*] Waiting for Kibana to be available ...")
    t0 = time.time()
    while True:
        try:
            r = requests.get(f"{KIBANA_URL}/api/status", timeout=10, headers={"kbn-xsrf":"true"})
            if r.ok:
                js = r.json()
                lvl = js.get("status", {}).get("overall", {}).get("level") or js.get("overall", {}).get("level")
                if lvl == "available":
                    log("[✓] Kibana status: available")
                    return
        except Exception:
            pass
        if time.time() - t0 > timeout:
            raise SystemExit("Timeout waiting for Kibana readiness.")
        time.sleep(3)

# -------- Data View (index-pattern) --------
def find_data_view():
    r = http("GET", "/api/saved_objects/_find?type=index-pattern&per_page=10000", "find data views")
    for so in r.json().get("saved_objects", []):
        a = so.get("attributes", {})
        if a.get("title") == INDEX_PATTERN or a.get("name") == DATA_VIEW_NAME:
            return so["id"]
    return None

def create_data_view():
    body = {
        "attributes": {
            "title": INDEX_PATTERN,
            "name": DATA_VIEW_NAME,
            "timeFieldName": TIME_FIELD
        }
    }
    r = http("POST", "/api/saved_objects/index-pattern", "create data view", data=j(body))
    return r.json()["id"]

def ensure_data_view():
    dv_id = find_data_view()
    if dv_id:
        log(f"[✓] Data View exists: id={dv_id} (name='{DATA_VIEW_NAME}', title='{INDEX_PATTERN}')")
        return dv_id
    log(f"[*] Creating Data View for '{INDEX_PATTERN}' (name '{DATA_VIEW_NAME}', time '{TIME_FIELD}') ...")
    dv_id = create_data_view()
    log(f"[✓] Created Data View: id={dv_id}")
    return dv_id

# -------- Dashboard (by-value Lens) --------
def find_dashboard_id(title):
    r = http("GET", f"/api/saved_objects/_find?type=dashboard&search_fields=title&search={title}&per_page=10000",
             "find dashboard")
    for so in r.json().get("saved_objects", []):
        if so.get("attributes", {}).get("title") == title:
            return so["id"]
    return None

def build_lens_attrs_by_value(dv_id, layer="layer-1"):
    state = {
        "query": {"language": "kuery", "query": ""},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer: {
                        "indexPatternId": dv_id,
                        "columns": {
                            "x": {
                                "label": TIME_FIELD,
                                "dataType": "date",
                                "operationType": "date_histogram",
                                "sourceField": TIME_FIELD,
                                "isBucketed": True,
                                "params": {"interval": "auto"}
                            },
                            "y": {
                                "label": f"Last value of {TEMP_FIELD}",
                                "dataType": "number",
                                "operationType": "last_value",
                                "sourceField": TEMP_FIELD,
                                "isBucketed": False,
                                "params": {"sortField": TIME_FIELD, "showArrayValues": False}
                            }
                        },
                        "columnOrder": ["x", "y"],
                        "incompleteColumns": {},
                        "sampling": 1
                    }
                }
            }
        },
        "visualization": {
            "legend": {"isVisible": True, "position": "right"},
            "preferredSeriesType": "line",
            "layers": [{
                "layerId": layer,
                "accessors": ["y"],
                "position": "top",
                "seriesType": "line",
                "xAccessor": "x",
                "yConfig": [],
                "layerType": "data"
            }]
        },
        "adHocDataViews": {}
    }
    return {
        "title": LENS_TITLE,
        "description": "By-value Lens via REST API",
        "visualizationType": "lnsXY",
        "state": state,
        "references": [
            {"type": "index-pattern", "id": dv_id, "name": f"indexpattern-datasource-layer-{layer}"}
        ]
    }

def upsert_dashboard_by_value(dv_id, lens_attrs, layer="layer-1"):
    panel_uid = "panel_0"
    panel = {
        "version": "8.15.0",
        "type": "lens",
        "embeddableConfig": {"attributes": lens_attrs, "hidePanelTitles": False},
        "gridData": {"x": 0, "y": 0, "w": 24, "h": 15, "i": panel_uid},
        "panelIndex": panel_uid
    }
    attrs = {
        "title": DASHBOARD_TITLE,
        "description": "Dashboard with by-value Lens",
        "panelsJSON": json.dumps([panel]),
        "optionsJSON": json.dumps({"hidePanelTitles": False}),
        "timeRestore": False
    }
    # Include index-pattern at top-level references (some builds expect this even for by-value)
    top_refs = [{"type": "index-pattern", "id": dv_id, "name": f"indexpattern-datasource-layer-{layer}"}]
    payload = {"attributes": attrs, "references": top_refs}

    dash_id = find_dashboard_id(DASHBOARD_TITLE)
    if dash_id:
        http("PUT", f"/api/saved_objects/dashboard/{dash_id}", "update dashboard", data=j(payload))
        log(f"[✓] Updated dashboard: {dash_id}")
        return dash_id
    else:
        r = http("POST", "/api/saved_objects/dashboard", "create dashboard", data=j(payload))
        dash_id = r.json()["id"]
        log(f"[✓] Created dashboard: {dash_id}")
        return dash_id

def validate_dashboard(dash_id, dv_id, layer="layer-1"):
    so = http("GET", f"/api/saved_objects/dashboard/{dash_id}", "get dashboard").json()
    refs = so.get("references", [])
    expect_name = f"indexpattern-datasource-layer-{layer}"
    has_ref = any(r.get("type")=="index-pattern" and r.get("id")==dv_id and r.get("name")==expect_name for r in refs)
    if not has_ref:
        log("[!] Warning: top-level references missing/incorrect. Attempting to fix ...")
        attrs = so.get("attributes", {})
        payload = {"attributes": attrs, "references": [{"type":"index-pattern","id":dv_id,"name":expect_name}]}
        http("PUT", f"/api/saved_objects/dashboard/{dash_id}", "fix references", data=j(payload))
    # quick parse of panels
    attrs = http("GET", f"/api/saved_objects/dashboard/{dash_id}", "re-get").json().get("attributes", {})
    panels = json.loads(attrs.get("panelsJSON","[]"))
    if not panels:
        raise SystemExit("No panels in dashboard after save.")
    emb = panels[0].get("embeddableConfig", {}).get("attributes", {})
    dv_in = emb.get("state",{}).get("datasourceStates",{}).get("formBased",{}).get("layers",{}).get(layer,{}).get("indexPatternId")
    if dv_in != dv_id:
        raise SystemExit(f"Lens layer indexPatternId mismatch: {dv_in} != {dv_id}")
    log("[✓] Dashboard validated.")

# -------- Main --------
if __name__ == "__main__":
    log("=== Kibana Dashboard Creator ===")
    log(f"KIBANA_URL={KIBANA_URL}")
    log(f"INDEX_PATTERN={INDEX_PATTERN} | DATA_VIEW_NAME={DATA_VIEW_NAME} | TIME_FIELD={TIME_FIELD}")
    log(f"DASHBOARD_TITLE={DASHBOARD_TITLE} | LENS_TITLE={LENS_TITLE} | TEMP_FIELD={TEMP_FIELD}")

    wait_kibana()

    dv_id = ensure_data_view()
    lens_attrs = build_lens_attrs_by_value(dv_id)
    dash_id = upsert_dashboard_by_value(dv_id, lens_attrs)
    validate_dashboard(dash_id, dv_id)

    url = f"{KIBANA_URL}/app/dashboards#/view/{dash_id}"
    log(f"\nOpen: {url}")

