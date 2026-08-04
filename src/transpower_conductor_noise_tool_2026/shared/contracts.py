import re

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import date, datetime
from typing import List

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class SiteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    noise_site_id: int
    site_name: str
    site_code: str | None = None


class SiteDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    noise_site_id: int
    site_name: str
    site_code: str | None = None
    plot_color: str | None = None
    height_adj_db: float = 0
    data_folder: str | None = None
    report_folder: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_ignored: bool = False


class SiteUpdate(BaseModel):
    site_code: str | None = None
    plot_color: str | None = None
    height_adj_db: float | None = None
    data_folder: str | None = None
    report_folder: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_ignored: bool | None = None

    @field_validator("plot_color")
    @classmethod
    def validate_plot_color(cls, value):
        if value is None or HEX_COLOR_PATTERN.match(value):
            return value
        raise ValueError("plot_color must be a hex color like #aabbcc")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value):
        if value is None or -90 <= value <= 90:
            return value
        raise ValueError("latitude must be between -90 and 90")

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value):
        if value is None or -180 <= value <= 180:
            return value
        raise ValueError("longitude must be between -180 and 180")


class ChartFilters(BaseModel):
    noise_site_id: List[int] = []
    start_date: date | None = None
    end_date: date | None = None
    condition: str = "all"
    parameter: str = "tone_100hz"
    interval_weeks: int = 2
    conductor_and_treatment: List[str] = []
    grease: List[str] = []
    plot_by: str = "datetime"
    measurement_duration: int = 15
    detection_logic: str = "original"

    @field_validator("interval_weeks")
    @classmethod
    def validate_interval_weeks(cls, value):
        if 1 <= value <= 4:
            return value
        raise ValueError("interval_weeks must be between 1 and 4")

    @field_validator("measurement_duration")
    @classmethod
    def validate_measurement_duration(cls, value):
        if value in {1, 15}:
            return value
        raise ValueError("measurement_duration must be 1 or 15")

    @field_validator("detection_logic")
    @classmethod
    def validate_detection_logic(cls, value):
        if value in {"original", "updated_2026"}:
            return value
        raise ValueError("detection_logic must be 'original' or 'updated_2026'")

    @field_validator("plot_by")
    @classmethod
    def validate_plot_by(cls, value):
        if value in {"datetime", "days_since_conductoring"}:
            return value
        raise ValueError("plot_by must be 'datetime' or 'days_since_conductoring'")


class ConductorSummaryFilters(BaseModel):
    noise_site_id: List[int] = []
    detection_logic: str = "original"
    measurement_duration_minutes: int = 15
    metric: str = "l90"

    @field_validator("detection_logic")
    @classmethod
    def validate_detection_logic(cls, value):
        if value in {"original", "updated_2026"}:
            return value
        raise ValueError("detection_logic must be 'original' or 'updated_2026'")

    @field_validator("measurement_duration_minutes")
    @classmethod
    def validate_measurement_duration_minutes(cls, value):
        if value in {1, 15}:
            return value
        raise ValueError("measurement_duration_minutes must be 1 or 15")

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, value):
        if value in {"l90", "tone_100hz", "tone_200hz"}:
            return value
        raise ValueError("metric must be 'l90', 'tone_100hz', or 'tone_200hz'")


class RainRateVsLevelFilters(BaseModel):
    noise_site_id: List[int] = []
    detection_logic: str = "original"
    metric: str = "l90"
    include_dry: bool = False

    @field_validator("detection_logic")
    @classmethod
    def validate_detection_logic(cls, value):
        if value in {"original", "updated_2026"}:
            return value
        raise ValueError("detection_logic must be 'original' or 'updated_2026'")

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, value):
        if value in {"l90", "tone_100hz", "tone_200hz"}:
            return value
        raise ValueError("metric must be 'l90', 'tone_100hz', or 'tone_200hz'")


class SiteListResponse(BaseModel):
    items: List[SiteSummary]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    write_access: bool


class ChartsResponse(BaseModel):
    noise_chart: dict
    timeline_chart: dict


class ChartTableRow(BaseModel):
    id: int
    noise_site_id: int
    site_name: str
    datetime: datetime
    conductor_and_treatment: str | None = None
    grease: str | None = None
    days_since_conductoring: float | None = None
    leq_adj: float
    tone_100hz: float
    tone_200hz: float
    rain1: float
    rain2: float
    is_wet: bool
    include: bool


class ChartTableResponse(BaseModel):
    items: List[ChartTableRow]


class ProcessedReadingUpdate(BaseModel):
    is_wet: bool | None = None
    include: bool | None = None


class OutageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    noise_site_id: int
    outage_type: str
    start_datetime: datetime
    end_datetime: datetime
    notes: str | None = None


class OutageCreate(BaseModel):
    noise_site_id: int
    outage_type: str
    start_datetime: datetime
    end_datetime: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_datetime_order(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self


class OutageUpdate(BaseModel):
    outage_type: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_datetime_order(self):
        if (
            self.start_datetime is not None
            and self.end_datetime is not None
            and self.end_datetime <= self.start_datetime
        ):
            raise ValueError("end_datetime must be after start_datetime")
        return self


class ReconductoringDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    noise_site_id: int
    conductor_and_treatment: str | None = None
    grease: str | None = None
    reconductoring_date: date
    notes: str | None = None


class ReconductoringCreate(BaseModel):
    noise_site_id: int
    conductor_and_treatment: str | None = None
    grease: str | None = None
    reconductoring_date: date
    notes: str | None = None


class ReconductoringUpdate(BaseModel):
    conductor_and_treatment: str | None = None
    grease: str | None = None
    reconductoring_date: date | None = None
    notes: str | None = None


class HistoricalResultDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    noise_site_id: int
    period_length: int
    period_end_date: date
    leq_adj: float | None = None
    tone_100hz: float | None = None


class HistoricalResultCreate(BaseModel):
    noise_site_id: int
    period_length: int = 2
    period_end_date: date
    leq_adj: float | None = None
    tone_100hz: float | None = None


class HistoricalResultUpdate(BaseModel):
    period_length: int | None = None
    period_end_date: date | None = None
    leq_adj: float | None = None
    tone_100hz: float | None = None
