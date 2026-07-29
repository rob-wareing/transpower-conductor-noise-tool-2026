from flask import Blueprint, jsonify, request, session

from transpower_conductor_noise_tool_2026.backend.domain.auth_service import (
    authenticate,
    get_user_by_id,
)
from transpower_conductor_noise_tool_2026.shared.contracts import UserSummary

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "")
    password = payload.get("password", "")

    user = authenticate(email, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"] = user.id
    return jsonify({"user": UserSummary.model_validate(user).model_dump()})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"status": "ok"})


@bp.get("/me")
def me():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"error": "not authenticated"}), 401

    user = get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "not authenticated"}), 401

    return jsonify({"user": UserSummary.model_validate(user).model_dump()})
