from datetime import datetime

from transpower_conductor_noise_tool_2026.backend.domain import processing_service
from transpower_conductor_noise_tool_2026.backend.domain import processing_service_updated_2026
from transpower_conductor_noise_tool_2026.backend.ingestion.nw_client import NoiseAndWeatherClient
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reading import Reading
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reading_repository import (
    ReadingRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.site_repository import (
    SiteRepository,
)

# Sites deliberately excluded from ingestion, carried over verbatim from the old
# app's operational exclusion list (site-owner requests / decommissioned / fully
# covered by historical data not yet ported here) — see
# application/services/processing_service.py::IGNORE_SITES in the old repo for the
# original per-site rationale comments.
IGNORE_SITES = {
    -1,
    51,
    87,
    106,
    121,
    123,
    124,
    129,
    134,
    135,
    136,
    145,
    146,
    158,
    162,
    163,
    179,
    203,
    205,
}

DEFAULT_START_DATETIME = datetime(2016, 1, 1)


def _get_start_datetime(reading_repository, noise_site_id):
    return reading_repository.latest_datetime(noise_site_id) or DEFAULT_START_DATETIME


def _reading_from_row(row):
    return Reading(
        noise_site_id=int(row["noise_site_id"]),
        datetime=row["datetime"],
        leq=row["leq"],
        l90=row["l90"],
        leq_80hz=row["leq_80hz"],
        leq_100hz=row["leq_100hz"],
        leq_125hz=row["leq_125hz"],
        leq_160hz=row["leq_160hz"],
        leq_200hz=row["leq_200hz"],
        leq_250hz=row["leq_250hz"],
        wind_speed=row["wind_speed"],
        wind_direction=row["wind_direction"],
        rain_mm=row["rain_mm"],
        # Always present by the time this runs - processing_service.add_leq_rmse
        # adds the column (currently always None, a placeholder - see there).
        # clean_leq_rmse converts a pandas-NaN missing value to a real SQL
        # NULL - PyMySQL rejects float('nan') outright.
        leq_rmse=processing_service.clean_leq_rmse(row["leq_rmse"]),
    )


def _processed_reading_from_row(row, detection_logic):
    return ProcessedReading(
        noise_site_id=int(row["noise_site_id"]),
        datetime=row["datetime"],
        l90=row["l90"],
        tone_100hz=row["tone_100hz"],
        tone_200hz=row["tone_200hz"],
        rain1=row["rain1"],
        rain2=row["rain2"],
        is_wet=bool(row["is_wet"]),
        include=bool(row["include"]),
        detection_logic=detection_logic,
        # Only the updated_2026 logic's own process_readings() adds a leq_rmse
        # column to its output rows (copying the raw Reading's value across for
        # measurements that pass its filters) - original-logic rows never carry
        # that key, so this naturally resolves to None for them via .get().
        # clean_leq_rmse converts a pandas-NaN missing value to a real SQL
        # NULL - PyMySQL rejects float('nan') outright.
        leq_rmse=processing_service.clean_leq_rmse(row.get("leq_rmse")),
    )


def collect_new_readings(
    client: NoiseAndWeatherClient | None = None,
    site_repository: SiteRepository | None = None,
    reading_repository: ReadingRepository | None = None,
    processed_reading_repository: ProcessedReadingRepository | None = None,
    site_ids: list[int] | None = None,
):
    client = client or NoiseAndWeatherClient()
    site_repository = site_repository or SiteRepository()
    reading_repository = reading_repository or ReadingRepository()
    processed_reading_repository = processed_reading_repository or ProcessedReadingRepository()

    known_site_ids = {site.noise_site_id for site in site_repository.list_sites()}
    allowed_site_ids = set(site_ids) if site_ids else None

    summary = {}
    for remote_site in client.sites():
        noise_site_id = int(remote_site["noise_site_id"])
        if noise_site_id in IGNORE_SITES:
            continue

        if allowed_site_ids is not None and noise_site_id not in allowed_site_ids:
            continue

        if noise_site_id not in known_site_ids:
            # The old app auto-created a local Site row here from the API's site
            # details. The exact field mapping for that isn't confirmed against
            # the real API response, so rather than fabricate it, sites unknown
            # locally are skipped — add them via the existing Site-seeding path
            # first (see data/site.csv) if ingestion needs to cover them.
            summary[noise_site_id] = {"skipped": "site not known locally"}
            continue

        start = _get_start_datetime(reading_repository, noise_site_id)

        try:
            raw_df = client.collect_events(
                site_id=remote_site["site_id"],
                noise_site_id=noise_site_id,
                period_start=start,
                period_end=datetime.now(),
            )
        except Exception as exc:
            summary[noise_site_id] = {"error": str(exc)}
            continue

        if raw_df is None or raw_df.empty:
            summary[noise_site_id] = {
                "readings": 0,
                "processed_readings_original": 0,
                "processed_readings_updated_2026": 0,
            }
            continue

        cleaned = processing_service.clean_readings(processing_service.rename_raw_columns(raw_df))
        cleaned = processing_service.add_leq_rmse(cleaned)

        readings = [_reading_from_row(row) for _, row in cleaned.iterrows()]
        reading_repository.upsert_readings(readings)

        # Both detection logics run off the same cleaned raw data and write their
        # own tagged ProcessedReading rows, side by side - "original" is never
        # replaced, just joined by "updated_2026".
        original_df = processing_service.process_readings(cleaned)
        updated_2026_df = processing_service_updated_2026.process_readings(cleaned)
        processed_readings = [
            _processed_reading_from_row(row, "original") for _, row in original_df.iterrows()
        ] + [
            _processed_reading_from_row(row, "updated_2026")
            for _, row in updated_2026_df.iterrows()
        ]
        processed_reading_repository.add_readings(processed_readings)

        summary[noise_site_id] = {
            "readings": len(readings),
            "processed_readings_original": len(original_df),
            "processed_readings_updated_2026": len(updated_2026_df),
        }

    return summary
