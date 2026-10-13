"""One-off check of candidate data sources. Prints schema, samples and volumes."""
import json, os, urllib.request, urllib.parse, datetime as dt

def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "nightly-311-pipeline-probe", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def section(t): print("\n" + "=" * 8 + " " + t + " " + "=" * 8, flush=True)

section("Cincinnati catalog: 311")
try:
    cat = get("https://data.cincinnati-oh.gov/api/catalog/v1?q=311&limit=15")
    ids = []
    for r in cat["results"]:
        res = r["resource"]
        print(res["id"], "|", res["name"], "|", res.get("data_updated_at"), "|", res.get("type"))
        if res.get("type") == "dataset": ids.append(res["id"])
except Exception as e:
    print("catalog error:", e); ids = []

for ds in ids[:4]:
    section(f"dataset {ds}")
    try:
        meta = get(f"https://data.cincinnati-oh.gov/api/views/{ds}.json")
        print("name:", meta.get("name"), "| rows updated:", meta.get("rowsUpdatedAt"))
        for c in meta.get("columns", []):
            print(f"  {c.get('fieldName'):40} {c.get('dataTypeName')}")
        rows = get(f"https://data.cincinnati-oh.gov/resource/{ds}.json?$limit=5&$order=:id DESC")
        for row in rows[:5]:
            print(json.dumps(row)[:900])
        # rough recent daily volume using the first date-like column
        dcols = [c["fieldName"] for c in meta.get("columns", []) if c.get("dataTypeName") in ("calendar_date", "date")]
        if dcols:
            d = dcols[0]
            since = (dt.date.today() - dt.timedelta(days=14)).isoformat()
            q = urllib.parse.quote(f"select date_trunc_ymd({d}) as day, count(*) as n where {d} >= '{since}' group by day order by day")
            print("volume by", d, get(f"https://data.cincinnati-oh.gov/resource/{ds}.json?$query={q}"))
    except Exception as e:
        print("error:", e)

section("NOAA CDO (CVG airport)")
try:
    end = dt.date.today(); start = end - dt.timedelta(days=10)
    url = ("https://www.ncei.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&stationid=GHCND:USW00093814"
           f"&startdate={start}&enddate={end}&units=standard&limit=50")
    d = get(url, {"token": os.environ.get("NOAA_TOKEN", "")})
    for r in d.get("results", [])[:20]: print(r)
    print("count:", d.get("metadata"))
except Exception as e:
    print("noaa error:", e)

section("CFPB complaints (fallback)")
try:
    d = get("https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?size=3&has_narrative=true&sort=created_date_desc")
    hits = d["hits"]["hits"]
    print("total with narrative:", d["hits"]["total"])
    for h in hits:
        s = h["_source"]
        print(s.get("date_received"), "|", s.get("product"), "|", s.get("issue"), "|", (s.get("complaint_what_happened") or "")[:200])
except Exception as e:
    print("cfpb error:", e)
