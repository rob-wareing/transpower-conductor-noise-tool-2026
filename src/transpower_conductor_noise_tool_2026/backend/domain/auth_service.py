from werkzeug.security import check_password_hash, generate_password_hash

from transpower_conductor_noise_tool_2026.backend.persistence.models.user import User
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.user_repository import (
    UserRepository,
)


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def authenticate(email: str, password: str, repository: UserRepository | None = None) -> User | None:
    repository = repository or UserRepository()
    user = repository.find_by_email(email)
    if user is None:
        return None
    if not check_password_hash(user.hashed_password, password):
        return None
    repository.touch_last_login(user)
    return user


def create_user(
    name: str,
    email: str,
    password: str,
    write_access: bool = False,
    repository: UserRepository | None = None,
) -> User:
    repository = repository or UserRepository()
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        write_access=write_access,
    )
    return repository.add_user(user)


def get_user_by_id(user_id: int, repository: UserRepository | None = None) -> User | None:
    repository = repository or UserRepository()
    return repository.find_by_id(user_id)
