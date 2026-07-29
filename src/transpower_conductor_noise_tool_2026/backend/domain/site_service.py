from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import SiteDetail, SiteSummary, SiteUpdate


def list_site_summaries(repository: SiteRepository | None = None) -> list[SiteSummary]:
    repository = repository or SiteRepository()
    return [SiteSummary.model_validate(site) for site in repository.list_sites()]


def list_site_details(repository: SiteRepository | None = None) -> list[SiteDetail]:
    repository = repository or SiteRepository()
    return [SiteDetail.model_validate(site) for site in repository.list_sites()]


def update_site_fields(noise_site_id: int, update: SiteUpdate, repository: SiteRepository | None = None):
    repository = repository or SiteRepository()
    site = repository.find_by_noise_site_id(noise_site_id)
    if site is None:
        return None

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(site, field, value)

    return repository.save(site)
