from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.ingestion.ingestion_job import (
    collect_new_readings,
)


def main():
    app = create_app(
        {
            "AUTO_INIT_DB": False,
            "AUTO_SEED_DATA": False,
        }
    )
    with app.app_context():
        summary = collect_new_readings(site_ids=app.config.get("INGEST_SITE_IDS"))
        for noise_site_id, result in summary.items():
            print(f"site={noise_site_id} {result}")


if __name__ == "__main__":
    main()
