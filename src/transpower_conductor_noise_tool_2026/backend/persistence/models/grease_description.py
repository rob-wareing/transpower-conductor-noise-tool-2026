from transpower_conductor_noise_tool_2026.backend.extensions import db


class GreaseDescription(db.Model):
    __tablename__ = "grease_description"

    grease = db.Column(db.String(20), primary_key=True)
    description = db.Column(db.String(255), nullable=False)
