from datetime import datetime
from time import sleep, time
from urllib.parse import urlencode

import pandas as pd
import pytz
import requests

from transpower_conductor_noise_tool_2026.backend.config import Settings

PAGE_SIZE = 100  # max page size allowed by the Noise and Weather API
PAGE_DELAY_SECONDS = 15 * 60 / 60  # soft self-throttle between paged requests


class LoginError(Exception):
    pass


class ResponseError(Exception):
    pass


def as_utc(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=pytz.UTC)


def as_timestamp_ms(dt_local: datetime) -> int:
    # The Noise and Weather API requires timestamps in UTC, so to retrieve data for
    # 12am NZ localtime you must provide the epoch timestamp for 12am UTC — this is
    # an error in the API's own implementation, carried over verbatim from the old repo.
    return 1000 * int(as_utc(dt_local).timestamp())


def _throttle(t0, delay_seconds=PAGE_DELAY_SECONDS):
    elapsed = time() - t0
    if elapsed < delay_seconds:
        sleep(delay_seconds - elapsed)
    return time()


class NoiseAndWeatherClient:
    def __init__(self, base_url=None, username=None, password=None, timeout=None):
        self.base_url = base_url or Settings.NW_BASE_URL
        self.username = username or Settings.NW_USERNAME
        self.password = password or Settings.NW_PASSWORD
        self.timeout = timeout or Settings.NW_REQUEST_TIMEOUT
        self._token = None

    def authenticate(self):
        if not self.username or not self.password:
            raise LoginError("NW_USERNAME/NW_PASSWORD are not configured")

        response = requests.post(
            f"{self.base_url}/authenticate",
            json={"email": self.username, "password": self.password},
            timeout=self.timeout,
        )
        if response.status_code != 200:
            raise LoginError(response.reason)

        self._token = response.json().get("token")
        return self._token

    def _headers(self):
        if self._token is None:
            self.authenticate()
        return {"x-access-token": self._token}

    def sites(self):
        response = requests.get(
            f"{self.base_url}/sites", headers=self._headers(), timeout=self.timeout
        )
        if response.status_code != 200:
            raise ResponseError(response.reason)
        return response.json()["sites"]

    def _events_page(self, site_id, start_timestamp, end_timestamp, page):
        url = (
            f"{self.base_url}/events/{site_id}/{start_timestamp}/{end_timestamp}/?"
            + urlencode({"page": page, "page_size": PAGE_SIZE})
        )
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)

        if response.status_code == 401:
            self.authenticate()
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)

        if response.status_code != 200:
            raise ResponseError(response.reason)
        return response.json()

    def events(self, site_id, start_timestamp, end_timestamp):
        t0 = time()
        page = 1
        payload = self._events_page(site_id, start_timestamp, end_timestamp, page)
        events = list(payload["events"])

        while payload["meta"]["has_more"]:
            page += 1
            payload = self._events_page(site_id, start_timestamp, end_timestamp, page)
            events += payload["events"]
            t0 = _throttle(t0)

        if not events:
            return None

        df = pd.DataFrame.from_records([event["noise_data"] for event in events])
        df["date_time"] = pd.to_datetime(df["date_time"], unit="ms")
        return df.set_index("date_time", drop=True)

    def collect_events(self, site_id, noise_site_id, period_start, period_end):
        start_timestamp = as_timestamp_ms(period_start) + 60000
        end_timestamp = as_timestamp_ms(period_end)

        df = self.events(site_id, start_timestamp, end_timestamp)
        if df is None:
            return None

        df["noise_site_id"] = noise_site_id
        return df
