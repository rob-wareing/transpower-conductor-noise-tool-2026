from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.user import User


class UserRepository:
    def find_by_email(self, email):
        return User.query.filter_by(email=email).first()

    def find_by_id(self, user_id):
        return db.session.get(User, user_id)

    def add_user(self, user):
        db.session.add(user)
        db.session.commit()
        return user

    def touch_last_login(self, user):
        user.last_login = datetime.now()
        db.session.commit()
