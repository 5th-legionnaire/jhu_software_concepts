

import base64, json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def _decode(cursor: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))

def _encode(d: dict) -> str:
    raw = json.dumps(d, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def _cursor_url(created_at: str, admitid: int = 99_999_999) -> str:
    tok = _encode({"created_at": created_at,
                   "admitid": admitid,
                   "_pointsToNextItems": True})
    return urlunparse(("https", "www.thegradcafe.com", "/survey",
                       "", urlencode({"cursor": tok}), ""))