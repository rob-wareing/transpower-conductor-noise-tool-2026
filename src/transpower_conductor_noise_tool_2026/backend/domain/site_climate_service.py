from types import SimpleNamespace

from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_rainfall_repository import (
    MonthlyRainfallRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.monthly_weather_stats_repository import (
    MonthlyWeatherStatsRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_repository import (
    OutageRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_availability_repository import (
    ReadingAvailabilityRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.wind_rose_repository import (
    WindRoseRepository,
)


def _year_month(value):
    # value is a (year, month) tuple or None - packed to a YYYYMM int so
    # repositories can filter with a single comparison rather than a
    # composite (year, month) tuple comparison, which SQLite doesn't support.
    return value[0] * 100 + value[1] if value else None


def get_wind_rose(
    noise_site_id: int,
    start: tuple[int, int] | None = None,
    end: tuple[int, int] | None = None,
    repository: WindRoseRepository | None = None,
):
    repository = repository or WindRoseRepository()
    rows = repository.list_sectors(
        noise_site_id=[noise_site_id],
        start_year_month=_year_month(start),
        end_year_month=_year_month(end),
    )
    return _collapse_wind_rose(rows)


def _collapse_wind_rose(rows):
    # wind_rose is stored per (site, year, month, sector) so a date range can
    # be scoped without re-querying the raw reading table; collapse back
    # down to one row per sector, weighting each bucket's avg_wind_speed by
    # its own sample_count so buckets with more readings count for more.
    by_sector: dict[str, dict] = {}
    for row in rows:
        bucket = by_sector.setdefault(row.direction_sector, {"sample_count": 0, "speed_total": 0.0})
        bucket["sample_count"] += row.sample_count
        bucket["speed_total"] += float(row.avg_wind_speed) * row.sample_count

    return [
        SimpleNamespace(
            direction_sector=sector,
            sample_count=bucket["sample_count"],
            avg_wind_speed=(
                bucket["speed_total"] / bucket["sample_count"] if bucket["sample_count"] else 0.0
            ),
        )
        for sector, bucket in sorted(by_sector.items())
    ]


def get_monthly_rainfall(
    noise_site_id: int,
    start: tuple[int, int] | None = None,
    end: tuple[int, int] | None = None,
    repository: MonthlyRainfallRepository | None = None,
):
    repository = repository or MonthlyRainfallRepository()
    rows = repository.list_months(
        noise_site_id=[noise_site_id],
        start_year_month=_year_month(start),
        end_year_month=_year_month(end),
    )
    return _collapse_monthly_rainfall(rows)


def _collapse_monthly_rainfall(rows):
    # monthly_rainfall is stored per (site, year, month) so a date range can
    # be scoped without re-querying the raw reading table; collapse back
    # down to one row per calendar month (1-12), summing total_rain and
    # weighting avg_rain_mm by each bucket's own sample_count.
    by_month: dict[int, dict] = {}
    for row in rows:
        bucket = by_month.setdefault(
            row.month, {"sample_count": 0, "total_rain": 0.0, "rain_total_weighted": 0.0}
        )
        bucket["sample_count"] += row.sample_count
        bucket["total_rain"] += float(row.total_rain)
        bucket["rain_total_weighted"] += float(row.avg_rain_mm) * row.sample_count

    return [
        SimpleNamespace(
            month=month,
            sample_count=bucket["sample_count"],
            total_rain=bucket["total_rain"],
            avg_rain_mm=(
                bucket["rain_total_weighted"] / bucket["sample_count"]
                if bucket["sample_count"]
                else 0.0
            ),
        )
        for month, bucket in sorted(by_month.items())
    ]


def get_monthly_weather_stats(
    noise_site_id: int,
    start: tuple[int, int] | None = None,
    end: tuple[int, int] | None = None,
    repository: MonthlyWeatherStatsRepository | None = None,
):
    # Already stored at (site, year, month) granularity - the exact shape
    # the range chart needs - so this is a straight range-filtered read, no
    # re-aggregation required.
    repository = repository or MonthlyWeatherStatsRepository()
    return repository.list_months(
        noise_site_id=[noise_site_id],
        start_year_month=_year_month(start),
        end_year_month=_year_month(end),
    )


def get_site_summary(
    noise_site_id: int,
    reconductoring_repository: ReconductoringRepository | None = None,
    outage_repository: OutageRepository | None = None,
    availability_repository: ReadingAvailabilityRepository | None = None,
    processed_reading_repository: ProcessedReadingRepository | None = None,
):
    # Bundles the four pieces the Locations tab shows for a clicked site into
    # one round trip rather than four - each piece comes from an existing,
    # already site-scoped repository method.
    reconductoring_repository = reconductoring_repository or ReconductoringRepository()
    outage_repository = outage_repository or OutageRepository()
    availability_repository = availability_repository or ReadingAvailabilityRepository()
    processed_reading_repository = processed_reading_repository or ProcessedReadingRepository()

    availability = availability_repository.find_by_site(noise_site_id)
    counts = processed_reading_repository.count_by_detection_logic(noise_site_id, include=True)

    return SimpleNamespace(
        reconductoring_events=reconductoring_repository.list_events(noise_site_id=noise_site_id),
        outages=outage_repository.list_outages(noise_site_id=noise_site_id),
        availability_start=availability.min_datetime if availability else None,
        availability_end=availability.max_datetime if availability else None,
        detected_event_count_original=counts["original"],
        detected_event_count_updated_2026=counts["updated_2026"],
    )
