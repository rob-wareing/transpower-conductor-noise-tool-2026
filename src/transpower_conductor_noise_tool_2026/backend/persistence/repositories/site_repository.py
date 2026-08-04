from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.site import Site


class SiteRepository:
    def list_sites(self, include_ignored=False):
        query = Site.query
        if not include_ignored:
            query = query.filter(Site.is_ignored.is_(False))
        return query.order_by(Site.noise_site_id.asc()).all()

    def count_sites(self):
        return Site.query.count()

    def add_sites(self, sites):
        for site in sites:
            db.session.add(site)
        db.session.commit()

    def find_by_noise_site_id(self, noise_site_id):
        return Site.query.filter_by(noise_site_id=noise_site_id).first()

    def save(self, site):
        db.session.commit()
        return site
