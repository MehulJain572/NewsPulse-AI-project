import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, jsonify, request

import db

JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 24

_is_dev = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    if _is_dev:
        JWT_SECRET = "aether-dev-" + secrets.token_hex(16)
        print("[WARN] JWT_SECRET not set. Generated random DEV secret. "
              "Sessions invalidated on restart. Set JWT_SECRET in production.")
    else:
        raise RuntimeError(
            "JWT_SECRET environment variable is required. "
            "Set it to a long random string before starting the server."
        )

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    if len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash):
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash
    return False


def _is_legacy_hash(stored_hash: str) -> bool:
    return len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash)


def _make_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing = db.get_user_by_username(username)
    if existing:
        return jsonify({"error": "Username already taken"}), 409

    user_id = db.create_user(username, _hash_password(password))
    token = _make_token(user_id, username)
    return jsonify({"token": token, "user_id": user_id, "username": username}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = db.get_user_by_username(username)
    if not user or not _verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid username or password"}), 401

    if _is_legacy_hash(user["password_hash"]):
        new_hash = _hash_password(password)
        db.update_password_hash(user["id"], new_hash)

    token = _make_token(user["id"], user["username"])
    return jsonify({"token": token, "user_id": user["id"], "username": user["username"]})


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    user = db.get_user_by_id(request.current_user["user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user_id": user["id"],
        "username": user["username"],
        "telegram_chat_id": user["telegram_chat_id"],
        "has_telegram": bool(user["telegram_chat_id"]),
        "linking_code": user["linking_code"],
    })


@auth_bp.route("/generate-link-code", methods=["POST"])
@token_required
def generate_link_code():
    code = secrets.token_hex(3).upper()
    db.set_linking_code(request.current_user["user_id"], code)
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "")
    return jsonify({
        "code": code,
        "bot_username": bot_username,
        "deep_link": f"https://t.me/{bot_username}?start={code}" if bot_username else "",
        "native_link": f"tg://resolve?domain={bot_username}&start={code}" if bot_username else "",
        "instructions": f"Message the bot: /link {code}",
    })
