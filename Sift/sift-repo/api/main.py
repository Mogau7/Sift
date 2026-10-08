import hashlib, hmac, os, re, secrets, sqlite3, time, json
from collections import defaultdict, deque
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from audit import grade

FETCH_URL = os.environ["FETCH_URL"]
SECRET = os.environ["FETCH_SECRET"].encode()
DB = os.environ.get("DB_PATH", "/data/sift.db")
if len(SECRET) < 16: raise SystemExit("FETCH_SECRET is too short")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def db():
    c = sqlite3.connect(DB, timeout=5); c.row_factory = sqlite3.Row
    return c


with db() as c:
    c.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
    c.execute("DELETE FROM audits WHERE created_at < ?", (int(time.time()) - 30 * 86400,))

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")


@app.middleware("http")
async def headers(req: Request, call_next):
    r = await call_next(req)
    r.headers.update({
        "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"})
    if req.url.path.startswith("/api"): r.headers["Cache-Control"] = "no-store"
    return r


HITS = defaultdict(deque) 


def limit(key, n, seconds):
    now = time.time(); q = HITS[key]
    while q and q[0] < now - seconds: q.popleft()
    if len(q) >= n: raise HTTPException(429, "Easy. Try again in a bit.")
    q.append(now)


class AuditIn(BaseModel):
    url: str = Field(min_length=3, max_length=2000)


class MailIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)


def client_ip(req):
    return req.client.host if req.client else "unknown"


def clean_url(raw):
    raw = raw.strip()
    if not re.match(r"^https?://", raw, re.I): raw = "https://" + raw
    try:
        u = urlparse(raw)
        port = u.port
    except ValueError:
        raise HTTPException(400, "That does not look like a public web address.")
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or len(u.hostname) > 253 \
            or port not in (None, 80, 443) or re.search(r"[\s\x00-\x1f]", raw):
        raise HTTPException(400, "That does not look like a public web address.")
    return raw


@app.post("/api/audit")
async def audit(body: AuditIn, req: Request):
    ip = client_ip(req)
    limit("a1" + ip, 6, 60); limit("a2" + ip, 40, 86400)
    url = clean_url(body.url)
    sig = hmac.new(SECRET, url.encode(), hashlib.sha256).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(FETCH_URL + "/fetch", json={"url": url}, headers={"X-Sig": sig})
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the page checker.")
    if r.status_code != 200: raise HTTPException(502, "Could not load that page. Is it public?")
    try:
        res = grade(r.json())
    except Exception:
        raise HTTPException(502, "Could not read that page.")
    aid = secrets.token_urlsafe(16); res["id"] = aid
    with db() as c:
        c.execute("INSERT INTO audits(id,url,score,result,created_at) VALUES(?,?,?,?,?)",
                  (aid, res["url"][:2000], res["score"], json.dumps(res), int(time.time())))
    return res


@app.get("/api/audit/{aid}")
def get_audit(aid: str, req: Request):
    limit("g" + client_ip(req), 60, 60)
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,32}", aid): raise HTTPException(404, "Not found.")
    with db() as c: row = c.execute("SELECT result FROM audits WHERE id=?", (aid,)).fetchone()
    if not row: raise HTTPException(404, "Not found.")
    return json.loads(row["result"])


@app.post("/api/waitlist")
def waitlist(body: MailIn, req: Request):
    limit("w" + client_ip(req), 5, 3600)
    e = body.email.strip().lower()
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s.]{2,}", e): raise HTTPException(400, "That email does not look right.")
    with db() as c: c.execute("INSERT OR IGNORE INTO waitlist(email,created_at) VALUES(?,?)", (e, int(time.time())))
    return {"ok": True}


app.mount("/", StaticFiles(directory="/app/web", html=True), name="web")
