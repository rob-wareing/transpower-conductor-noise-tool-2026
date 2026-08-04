from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_rainfall_repository import (
    MonthlyRainfallRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.wind_rose_repository import (
    WindRoseRepository,
)


def get_wind_rose(noise_site_id: int, repository: WindRoseRepository | None = None):
    repository = repository or WindRoseRepository()
    return repository.list_sectors(noise_site_id=[noise_site_id])


def get_monthly_rainfall(noise_site_id: int, repository: MonthlyRainfallRepository | None = None):
    repository = repository or MonthlyRainfallRepository()
    return repository.list_months(noise_site_id=[noise_site_id])
