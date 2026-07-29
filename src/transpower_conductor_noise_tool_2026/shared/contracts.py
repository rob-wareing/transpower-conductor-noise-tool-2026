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


class SiteUpdate(BaseModel):
    site_code: str | None = None
    plot_color: str | None = None
    height_adj_db: float | None = None
    data_folder: str | None = None
    report_folder: str | None = None

    @field_validator("plot_color")
    @classmethod
    def validate_plot_color(cls, value):
        if value is None or HEX_COLOR_PATTERN.match(value):
            return value
        raise ValueError("plot_color must be a hex color like #aabbcc")


class ChartFilters(BaseModel):
    noise_site_id: List[int] = []
    start_date: date | None = None
    end_date: date | None = None
    condition: str = "all"
    parameter: str = "tone_100hz"


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
