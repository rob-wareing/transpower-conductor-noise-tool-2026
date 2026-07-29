from transpower_conductor_noise_tool_2026.backend.extensions import db


class Site(db.Model):
    __tablename__ = "site"

    id = db.Column(db.Integer, primary_key=True)
    noise_site_id = db.Column(db.Integer, nullable=False, unique=True)
    site_name = db.Column(db.String(100), nullable=False)
    site_code = db.Column(db.String(20), nullable=True)
    plot_color = db.Column(db.String(7), nullable=True)
    height_adj_db = db.Column(db.Numeric(4, 2), nullable=False, default=0)
    data_folder = db.Column(db.String(500), nullable=True)
    report_folder = db.Column(db.String(500), nullable=True)
