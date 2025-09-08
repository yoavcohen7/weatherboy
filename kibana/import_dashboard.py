import os, sys, json, time
import requests

# ENV variables
KIBANA_URL = os.getenv("KIBANA_URL", "http://kibana:5601").rstrip("/")
DASHBOARD_FILE = os.getenv("DASHBOARD_FILE", "kibana/dashboard_source.json")

DATA_VIEW_ID = os.getenv("DATA_VIEW_ID", "").strip()
DATA_VIEW_TITLE = os.getenv("DATA_VIEW_TITLE", "rabbitmq-logs*").strip()
DATA_VIEW_NAME = os.getenv("DATA_VIEW_NAME", "RabbitMQ Logs").strip()
TIME_FIELD = os.getenv("TIME_FIELD", "@timestamp").strip()

CREATE_DV = os.getenv("CREATE_DATAVIEW_IF_MISSING", "1").lower() in ("1","true","yes","y")
USE_EXISTING_ID = os.getenv("USE_EXISTING_ID", "").lower() in ("1","true","yes","y")
DEBUG = os.getenv("DEBUG", "").lower() in ("1","true","yes","y")

AUTH=None

if os.getenv("KIBANA_USERNAME") and os.getenv("KIBANA_PASSWORD"):
    AUTH=(os.getenv("KIBANA_USERNAME"), os.getenv("KIBANA_PASSWORD"))

HDR={"kbn-xsrf":"true","Content-Type":"application/json","Accept":"application/json"}

def log(m): print(m, flush=True) """Print a message right away so it shows up in the container logs."""
def j(x):  return json.dumps(x, ensure_ascii=False)"""Turn a Python object into a JSON string."""

def http(method, path, desc, **kw):
    """Send a request to Kibana with standard headers; show debug info if on; fail on bad status."""
    url=f"{KIBANA_URL}{path}"
    if DEBUG:
        b=kw.get("data") if "data" in kw else kw.get("json")
        log(f"[HTTP] {method} {url} -- {desc}")
        if b is not None:
            s=b if isinstance(b,str) else j(b)
            log("       payload: " + (s[:1400] + ("...(truncated)" if len(s)>1400 else "")))
    r=requests.request(method, url, headers=HDR, auth=AUTH, timeout=60, **kw)
    if DEBUG:
        try: log("       resp: " + j(r.json()))
        except: log("       resp(text): " + ((r.text or "")[:1400]))
    r.raise_for_status()
    return r

def wait_kibana(timeout=600):
    """Keep checking Kibana until it says “available,” or give up after a timeout."""
    log("[*] Waiting for Kibana to be 'available' ...")
    t0=time.time()
    while True:
        try:
            r=requests.get(f"{KIBANA_URL}/api/status", headers={"kbn-xsrf":"true"}, timeout=10)
            if r.ok:
                js=r.json()
                lvl=js.get("status",{}).get("overall",{}).get("level") or js.get("overall",{}).get("level")
                if lvl=="available":
                    log("[✓] Kibana available."); return
        except Exception: pass
        if time.time()-t0>timeout: raise SystemExit("Timeout waiting for Kibana.")
        time.sleep(3)

def list_data_views():"""Get all data views (index patterns) from Kibana."""
    return http("GET","/api/saved_objects/_find?type=index-pattern&per_page=10000","list data views").json().get("saved_objects",[])

def create_data_view(title,name,time_field):"""create a new data view with a title, name, and time field; return its ID. works only if prior dataview creation does not work"""
    body={"attributes":{"title":title,"name":name,"timeFieldName":time_field}}
    return http("POST","/api/saved_objects/index-pattern","create data view",data=j(body)).json()["id"]

def resolve_dataview_id(prefer_id,title_hint,create_if_missing):
    """Decide which data view ID to use (by ID or name), creating one if allowed."""
    items=list_data_views()
    if prefer_id:
        if any(so.get("id")==prefer_id for so in items):
            log(f"[✓] Using DATA_VIEW_ID={prefer_id}"); return prefer_id
        log(f"[!] DATA_VIEW_ID={prefer_id} not found.")
    if title_hint:
        for so in items:
            a=so.get("attributes",{})
            if a.get("title")==title_hint or a.get("name")==title_hint:
                log(f"[✓] Found DV '{title_hint}': {so['id']}"); return so["id"]
        q=title_hint.lower()
        for so in items:
            a=so.get("attributes",{})
            if q in (a.get("title","")+a.get("name","")).lower():
                log(f"[✓] Found DV containing '{title_hint}': {so['id']}"); return so["id"]
    if create_if_missing and title_hint:
        log(f"[*] Creating Data View: title='{title_hint}', name='{DATA_VIEW_NAME}', timeField='{TIME_FIELD}'")
        dv_id=create_data_view(title_hint, DATA_VIEW_NAME, TIME_FIELD)
        log(f"[✓] Created DV id={dv_id}"); return dv_id
    if len(items)==1:
        so=items[0]; log(f"[~] Defaulting to only DV: {so['id']}"); return so["id"]
    details=[{"id":so["id"],"title":so.get("attributes",{}).get("title"),"name":so.get("attributes",{}).get("name")} for so in items]
    raise SystemExit("Could not resolve a Data View ID. Set DATA_VIEW_ID or DATA_VIEW_TITLE.\nExisting: "+j(details))

def load_source(path): """Read the dashboard JSON file into a Python dictionary."""
    with open(path,"r",encoding="utf-8") as f: 
        return json.load(f)

def get_panels_from_attrs(attrs):
    """Pull the panels list from the dashboard (from panels or parsed from panelsJSON)."""
    if isinstance(attrs.get("panels"), list): return attrs["panels"], "panels"
    pj=attrs.get("panelsJSON")
    if isinstance(pj, list): return pj, "panelsJSON"
    if isinstance(pj, str) and pj.strip():
        try: return json.loads(pj), "panelsJSON"
        except Exception as e: raise SystemExit(f"panelsJSON is not valid JSON: {e}")
    return [], "none"

def ensure_search_source(attrs: dict):
    """Ensure dashboard has kibanaSavedObjectMeta.searchSourceJSON set."""
    k = attrs.get("kibanaSavedObjectMeta")
    if not isinstance(k, dict): k = {}
    if not k.get("searchSourceJSON"):
        default_ss = {"query":{"language":"kuery","query":""},"filter":[]}
        k["searchSourceJSON"] = json.dumps(default_ss, separators=(",", ":"), ensure_ascii=False)
        attrs["kibanaSavedObjectMeta"] = k

def patch_dashboard(source: dict, dv_id: str) -> dict:
    """"""
    attrs = dict(source.get("attributes", {}))
    refs  = list(source.get("references", []))

    # MUST have searchSourceJSON to avoid Kibana UI error
    ensure_search_source(attrs)

    # Patch top-level index-pattern references
    for r in refs:
        if r.get("type")=="index-pattern":
            r["id"]=dv_id

    # Extract panels (array), patch inner refs and indexPatternId
    panels, _ = get_panels_from_attrs(attrs)
    for p in panels:
        emb=p.get("embeddableConfig",{})
        at =emb.get("attributes",{})
        if isinstance(at,dict) and isinstance(at.get("references"),list):
            for rr in at["references"]:
                if rr.get("type")=="index-pattern":
                    rr["id"]=dv_id
        try:
            layers=at["state"]["datasourceStates"]["formBased"]["layers"]
            for _,layer in layers.items():
                if isinstance(layer,dict) and "indexPatternId" in layer:
                    layer["indexPatternId"]=dv_id
        except Exception:
            pass

    # Serialize to panelsJSON (what Kibana expects)
    attrs["panelsJSON"]=json.dumps(panels, separators=(",", ":"), ensure_ascii=False)
    if "panels" in attrs: del attrs["panels"]

    return {"attributes": attrs, "references": refs}

def create_or_update(payload: dict, source: dict) -> str:
    """Create a new dashboard or update the one from the file; return its ID."""
    if USE_EXISTING_ID and source.get("id"):
        dash_id=source["id"]
        http("PUT", f"/api/saved_objects/dashboard/{dash_id}", "update dashboard", data=j(payload))
        log(f"[✓] Updated dashboard id={dash_id}")
        return dash_id
    r=http("POST","/api/saved_objects/dashboard","create dashboard",data=j(payload))
    dash_id=r.json().get("id"); log(f"[✓] Created dashboard id={dash_id}")
    return dash_id

def main():
    log("=== Import Kibana Dashboard ===")
    log(f"KIBANA_URL={KIBANA_URL}")
    log(f"DASHBOARD_FILE={DASHBOARD_FILE}")
    wait_kibana()
    source=load_source(DASHBOARD_FILE)
    dv_id=resolve_dataview_id(DATA_VIEW_ID, DATA_VIEW_TITLE, CREATE_DV)
    payload=patch_dashboard(source, dv_id)
    dash_id=create_or_update(payload, source)
    log(f"[OPEN] {KIBANA_URL}/app/dashboards#/view/{dash_id}")

if __name__=="__main__":
    try: main()
    except requests.HTTPError as e:
        log("[HTTP ERROR] "+str(e)); log((e.response.text or "")[:1400]); sys.exit(1)
    except SystemExit as e:
        log(str(e)); sys.exit(1)
    except Exception as e:
        log("[FATAL] "+str(e)); sys.exit(1)
