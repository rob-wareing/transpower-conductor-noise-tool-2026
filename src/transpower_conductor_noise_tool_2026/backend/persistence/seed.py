from pathlib import Path

import pandas as pd

from transpower_conductor_noise_tool_2026.backend.domain.auth_service import hash_password
from transpower_conductor_noise_tool_2026.backend.extensions import db
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage import Outage
from transpower_conductor_noise_tool_2026.backend.persistence.models.outage_type import OutageType
from transpower_conductor_noise_tool_2026.backend.persistence.models.processed_reading import (
    ProcessedReading,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)
from transpower_conductor_noise_tool_2026.backend.persistence.models.site import Site
from transpower_conductor_noise_tool_2026.backend.persistence.models.user import User


def _clean_optional_value(value):
    if pd.isna(value):
        return None
    return value


def seed_sites_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if Site.query.count():
        return 0

    df = pd.read_csv(csv_path)
    for record in df.to_dict("records"):
        db.session.add(
            Site(
                id=int(record["id"]),
                noise_site_id=int(record["noise_site_id"]),
                site_name=str(record["site_name"]),
                site_code=_clean_optional_value(record.get("site_code")),
                plot_color=_clean_optional_value(record.get("plot_color")),
                height_adj_db=_clean_optional_value(record.get("height_adj_db"))
                or 0,
                data_folder=_clean_optional_value(record.get("data_folder")),
                report_folder=_clean_optional_value(record.get("report_folder")),
            )
        )

    db.session.commit()
    return len(df)


def seed_processed_readings_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if ProcessedReading.query.count():
        return 0

    df = pd.read_csv(csv_path, parse_dates=["datetime"])
    for record in df.to_dict("records"):
        db.session.add(
            ProcessedReading(
                id=int(record["id"]),
                noise_site_id=int(record["noise_site_id"]),
                datetime=record["datetime"],
                l90=record["l90"],
                tone_100hz=record["tone_100hz"],
                tone_200hz=record["tone_200hz"],
                rain1=record["rain1"],
                rain2=record["rain2"],
                is_wet=bool(record["is_wet"]),
                include=bool(record.get("include", True)),
            )
        )

    db.session.commit()
    return len(df)


def seed_outage_types_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if OutageType.query.count():
        return 0

    df = pd.read_csv(csv_path)
    for record in df.to_dict("records"):
        db.session.add(OutageType(outage_type=str(record["outage_type"])))

    db.session.commit()
    return len(df)


def seed_outages_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if Outage.query.count():
        return 0

    df = pd.read_csv(csv_path, parse_dates=["start_datetime", "end_datetime"])
    for record in df.to_dict("records"):
        db.session.add(
            Outage(
                id=int(record["id"]),
                noise_site_id=int(record["noise_site_id"]),
                outage_type=str(record["outage_type"]),
                start_datetime=record["start_datetime"],
                end_datetime=record["end_datetime"],
                notes=_clean_optional_value(record.get("notes")),
            )
        )

    db.session.commit()
    return len(df)


def seed_reconductoring_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if Reconductoring.query.count():
        return 0

    df = pd.read_csv(csv_path, parse_dates=["reconductoring_date"])
    for record in df.to_dict("records"):
        db.session.add(
            Reconductoring(
                id=int(record["id"]),
                noise_site_id=int(record["noise_site_id"]),
                conductor=_clean_optional_value(record.get("conductor")),
                grease=_clean_optional_value(record.get("grease")),
                conductor_and_treatment=_clean_optional_value(
                    record.get("conductor_and_treatment")
                ),
                reconductoring_date=record["reconductoring_date"].date(),
                plot_linestyle=_clean_optional_value(record.get("plot_linestyle")),
                notes=_clean_optional_value(record.get("notes")),
            )
        )

    db.session.commit()
    return len(df)


def seed_users_from_csv(csv_path: Path):
    if not csv_path.exists():
        return 0

    if User.query.count():
        return 0

    df = pd.read_csv(csv_path)
    for record in df.to_dict("records"):
        db.session.add(
            User(
                id=int(record["id"]),
                name=str(record["name"]),
                email=str(record["email"]),
                hashed_password=hash_password(str(record["password"])),
                write_access=bool(record.get("write_access", False)),
            )
        )

    db.session.commit()
    return len(df)
