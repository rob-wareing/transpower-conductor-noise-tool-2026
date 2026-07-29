from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.persistence.seed import (
    seed_outage_types_from_csv,
    seed_outages_from_csv,
    seed_processed_readings_from_csv,
    seed_reconductoring_from_csv,
    seed_sites_from_csv,
    seed_users_from_csv,
)


def main():
    app = create_app(
        {
            "AUTO_INIT_DB": False,
            "AUTO_SEED_DATA": False,
        }
    )
    with app.app_context():
        inserted_sites = seed_sites_from_csv(app.config["SITE_FIXTURE_PATH"])
        print(f"seeded_sites={inserted_sites}")
        inserted_users = seed_users_from_csv(app.config["USER_FIXTURE_PATH"])
        print(f"seeded_users={inserted_users}")
        inserted_readings = seed_processed_readings_from_csv(
            app.config["PROCESSED_READING_FIXTURE_PATH"]
        )
        print(f"seeded_processed_readings={inserted_readings}")
        inserted_outage_types = seed_outage_types_from_csv(app.config["OUTAGE_TYPE_FIXTURE_PATH"])
        print(f"seeded_outage_types={inserted_outage_types}")
        inserted_outages = seed_outages_from_csv(app.config["OUTAGE_FIXTURE_PATH"])
        print(f"seeded_outages={inserted_outages}")
        inserted_reconductoring = seed_reconductoring_from_csv(
            app.config["RECONDUCTORING_FIXTURE_PATH"]
        )
        print(f"seeded_reconductoring={inserted_reconductoring}")


if __name__ == "__main__":
    main()
