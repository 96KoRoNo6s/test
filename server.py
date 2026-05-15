import json
import os
import tempfile
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request


app = Flask(__name__)

DATA_DIR = Path(os.environ.get("AMM_DATA_DIR", "data")).resolve()
STORAGE_KEY = os.environ.get("AMM_STORAGE_KEY", "").strip()
MARKET_AUTH_KEY = os.environ.get("MARKET_AUTH_KEY", os.environ.get("MASTER_KEY", "")).strip()
MARKET_API_BASE = os.environ.get("MARKET_API_BASE", "https://api.arz.market/api").rstrip("/")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "12"))

ALLOWED_DOCS = {
    "users": "users.json",
    "keys": "keys.json",
    "bans": "bans.json",
    "items": "items.json",
    "market_cache": "market_cache.json",
    "market_actual": "market_actual.json",
}


def _split_env_list(value: str) -> set[str]:
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


STATIC_CLIENT_KEYS = _split_env_list(os.environ.get("AMM_CLIENT_KEYS", ""))


def _doc_path(name: str) -> Path:
    if name not in ALLOWED_DOCS:
        raise KeyError(name)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / ALLOWED_DOCS[name]


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _json_body(default=None):
    if default is None:
        default = {}
    data = request.get_json(silent=True)
    if data is not None:
        return data
    if request.data:
        try:
            return json.loads(request.data.decode("utf-8", errors="replace"))
        except Exception:
            return default
    return default


def _bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def request_key() -> str:
    body = _json_body({})
    return (
        request.headers.get("X-Storage-Key")
        or request.headers.get("X-Client-Key")
        or request.headers.get("authKey")
        or _bearer_token()
        or request.args.get("storageKey")
        or request.args.get("key")
        or request.args.get("authKey")
        or body.get("storageKey")
        or body.get("key")
        or body.get("authKey")
        or ""
    ).strip()


def require_storage_key():
    if not STORAGE_KEY:
        return jsonify({"ok": False, "error": "AMM_STORAGE_KEY is not configured"}), 503
    if request_key() != STORAGE_KEY:
        return jsonify({"ok": False, "error": "No access"}), 403
    return None


def users_doc() -> dict:
    return _read_json(_doc_path("users"), {})


def keys_doc() -> dict:
    return _read_json(_doc_path("keys"), {})


def is_access_active(user: dict) -> bool:
    return float(user.get("access_until") or 0) > time.time()


def find_user_by_script_key(script_key: str):
    script_key = str(script_key or "").upper().strip()
    if not script_key:
        return None, None
    for uid, user in users_doc().items():
        if isinstance(user, dict) and str(user.get("script_key") or user.get("lua_key") or "").upper() == script_key:
            return str(uid), user
    return None, None


def find_user_by_config_key(config_key: str):
    config_key = str(config_key or "").upper().strip()
    if not config_key:
        return None, None
    for uid, user in users_doc().items():
        if isinstance(user, dict) and str(user.get("config_key") or "").upper() == config_key:
            return str(uid), user
    return None, None


def client_key_allowed(key: str) -> bool:
    key = str(key or "").strip()
    if not key:
        return False
    if key == STORAGE_KEY or key in STATIC_CLIENT_KEYS:
        return True
    _, user = find_user_by_script_key(key)
    return bool(user and is_access_active(user))


def public_user_config(user: dict) -> dict:
    allowed = (
        "server",
        "sort",
        "mode",
        "min_notify_profit",
        "deal_search_min_profit",
        "comm_sa",
        "comm_vc",
        "notif_on",
        "notif_servers",
        "typo_alert_on",
        "typo_alert_servers",
        "typo_ratio",
        "cross_notif_on",
        "cross_notif_routes",
        "notif_profit_thresholds",
        "typo_profit_thresholds",
        "cross_profit_thresholds",
        "notif_interval",
        "typo_interval",
        "smart_dedup",
    )
    return {key: user.get(key) for key in allowed if key in user}


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "storage": bool(STORAGE_KEY),
        "market_proxy": bool(MARKET_AUTH_KEY),
        "docs": sorted(ALLOWED_DOCS),
    })


@app.get("/")
def index():
    return health()


@app.get("/api/storage")
def storage_index():
    denied = require_storage_key()
    if denied:
        return denied
    docs = {}
    for name in ALLOWED_DOCS:
        path = _doc_path(name)
        docs[name] = {
            "file": ALLOWED_DOCS[name],
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
            "updated_at": path.stat().st_mtime if path.exists() else 0,
        }
    return jsonify({"ok": True, "docs": docs})


@app.route("/api/storage/<name>", methods=["GET", "PUT", "PATCH"])
def storage_doc(name):
    denied = require_storage_key()
    if denied:
        return denied
    try:
        path = _doc_path(name)
    except KeyError:
        return jsonify({"ok": False, "error": "Unknown storage document"}), 404

    if request.method == "GET":
        if not path.exists():
            return jsonify({"ok": False, "error": "storage document not found"}), 404
        return jsonify(_read_json(path, {}))

    body = _json_body(None)
    if body is None or not isinstance(body, (dict, list)):
        return jsonify({"ok": False, "error": "JSON object or array expected"}), 400

    if request.method == "PATCH":
        old = _read_json(path, {})
        if not isinstance(old, dict) or not isinstance(body, dict):
            return jsonify({"ok": False, "error": "PATCH requires JSON objects"}), 400
        old.update(body)
        body = old

    _write_json(path, body)
    return jsonify({"ok": True, "name": name, "updated_at": time.time()})


@app.get("/api/lua/access/<script_key>")
def lua_access(script_key):
    uid, user = find_user_by_script_key(script_key)
    if not user:
        return jsonify({"ok": False, "error": "key not found"}), 404
    active = is_access_active(user)
    return jsonify({
        "ok": active,
        "user_id": uid,
        "access_until": user.get("access_until", 0),
        "error": "" if active else "access expired",
    }), 200 if active else 403


@app.get("/api/lua/config/<config_key>")
def lua_config(config_key):
    uid, user = find_user_by_config_key(config_key)
    if not user:
        return jsonify({"ok": False, "error": "config key not found"}), 404
    active = is_access_active(user)
    if not active:
        return jsonify({"ok": False, "error": "access expired", "access_until": user.get("access_until", 0)}), 403
    return jsonify({
        "ok": True,
        "user_id": uid,
        "access_until": user.get("access_until", 0),
        "config": public_user_config(user),
    })


@app.get("/api/public/items")
def public_items():
    return jsonify(_read_json(_doc_path("items"), {}))


def upstream_market(path: str, server_id: str):
    if not MARKET_AUTH_KEY:
        return jsonify({"ok": False, "error": "MARKET_AUTH_KEY is not configured"}), 503

    client_key = request_key()
    if not client_key_allowed(client_key):
        return jsonify({"ok": False, "error": "No access"}), 403

    body = _json_body({})
    if not isinstance(body, dict):
        body = {}
    sid = str(body.get("serverId") or body.get("server") or server_id or "-1")
    payload = dict(body)
    payload["authToken"] = MARKET_AUTH_KEY
    payload["authKey"] = "nil"
    payload["serverId"] = sid

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "User-Agent": "LuaSocket 3.0-rc1",
        "authKey": MARKET_AUTH_KEY,
        "Authorization": f"Bearer {MARKET_AUTH_KEY}",
        "Origin": "https://arz.market",
        "Referer": "https://arz.market/",
    }
    url = f"{MARKET_API_BASE}/{path.rstrip('/')}/{sid}"
    try:
        if request.method == "GET":
            resp = requests.get(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        else:
            resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        return (resp.text, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except requests.RequestException as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/selectMarketplace/", defaults={"server_id": "-1"}, methods=["GET", "POST"])
@app.route("/api/selectMarketplace/<server_id>", methods=["GET", "POST"])
def select_marketplace(server_id):
    return upstream_market("selectMarketplace", server_id)


@app.route("/api/getSelectedMarketplace/<server_id>", methods=["GET", "POST"])
def selected_marketplace(server_id):
    return upstream_market("getSelectedMarketplace", server_id)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
