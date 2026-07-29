from functools import wraps

from flask import jsonify, session

from transpower_conductor_noise_tool_2026.backend.domain.auth_service import get_user_by_id


def require_write_access(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        user = get_user_by_id(user_id) if user_id is not None else None

        if user is None:
            return jsonify({"error": "not authenticated"}), 401
        if not user.write_access:
            return jsonify({"error": "write access required"}), 403

        return fn(*args, **kwargs)

    return wrapper
