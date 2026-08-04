from dataclasses import dataclass

import requests

from transpower_conductor_noise_tool_2026.shared.contracts import (
    ChartFilters,
    ChartTableRow,
    ConductorSummaryFilters,
    HistoricalResultCreate,
    HistoricalResultDetail,
    HistoricalResultUpdate,
    OutageCreate,
    OutageDetail,
    OutageUpdate,
    ProcessedReadingUpdate,
    RainRateVsLevelFilters,
    ReconductoringCreate,
    ReconductoringDetail,
    ReconductoringUpdate,
    SiteDetail,
    SiteSummary,
    SiteUpdate,
    UserSummary,
)


@dataclass
class BackendClient:
    base_url: str

    def get_sites(self):
        response = requests.get(f"{self.base_url}/api/sites", timeout=10)
        response.raise_for_status()
        return [SiteSummary.model_validate(item) for item in response.json()["items"]]

    def login(self, email: str, password: str):
        return requests.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )

    def logout(self, cookies):
        return requests.post(f"{self.base_url}/api/auth/logout", cookies=cookies, timeout=10)

    def get_current_user(self, cookies) -> UserSummary | None:
        response = requests.get(f"{self.base_url}/api/auth/me", cookies=cookies, timeout=10)
        if response.status_code == 401:
            return None
        response.raise_for_status()
        return UserSummary.model_validate(response.json()["user"])

    def get_site_details(self, include_ignored: bool = False):
        response = requests.get(
            f"{self.base_url}/api/sites/detail",
            params={"include_ignored": "true"} if include_ignored else None,
            timeout=10,
        )
        response.raise_for_status()
        return [SiteDetail.model_validate(item) for item in response.json()["items"]]

    def update_site(self, noise_site_id: int, update: SiteUpdate, cookies):
        return requests.patch(
            f"{self.base_url}/api/sites/{noise_site_id}",
            json=update.model_dump(exclude_unset=True, mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def get_charts(self, filters: ChartFilters):
        response = requests.post(
            f"{self.base_url}/api/charts",
            json=filters.model_dump(mode="json"),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_conductor_summary_chart(self, filters: ConductorSummaryFilters):
        response = requests.post(
            f"{self.base_url}/api/trends/conductor-summary",
            json=filters.model_dump(mode="json"),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["conductor_summary_chart"]

    def get_rain_rate_vs_level_chart(self, filters: RainRateVsLevelFilters):
        response = requests.post(
            f"{self.base_url}/api/trends/rain-rate-vs-level",
            json=filters.model_dump(mode="json"),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["rain_rate_vs_level_chart"]

    def get_chart_table_rows(self, filters: ChartFilters):
        response = requests.post(
            f"{self.base_url}/api/charts/table",
            json=filters.model_dump(mode="json"),
            timeout=30,
        )
        response.raise_for_status()
        return [ChartTableRow.model_validate(item) for item in response.json()["items"]]

    def update_processed_reading(self, reading_id: int, update: ProcessedReadingUpdate, cookies):
        return requests.patch(
            f"{self.base_url}/api/processed-readings/{reading_id}",
            json=update.model_dump(exclude_unset=True, mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def get_outages(self):
        response = requests.get(f"{self.base_url}/api/outages", timeout=10)
        response.raise_for_status()
        return [OutageDetail.model_validate(item) for item in response.json()["items"]]

    def get_outage_types(self):
        response = requests.get(f"{self.base_url}/api/outages/types", timeout=10)
        response.raise_for_status()
        return response.json()["items"]

    def create_outage(self, data: OutageCreate, cookies):
        return requests.post(
            f"{self.base_url}/api/outages",
            json=data.model_dump(mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def update_outage(self, outage_id: int, update: OutageUpdate, cookies):
        return requests.patch(
            f"{self.base_url}/api/outages/{outage_id}",
            json=update.model_dump(exclude_unset=True, mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def delete_outage(self, outage_id: int, cookies):
        return requests.delete(
            f"{self.base_url}/api/outages/{outage_id}", cookies=cookies, timeout=10
        )

    def get_reconductoring_events(self):
        response = requests.get(f"{self.base_url}/api/reconductoring", timeout=10)
        response.raise_for_status()
        return [ReconductoringDetail.model_validate(item) for item in response.json()["items"]]

    def create_reconductoring_event(self, data: ReconductoringCreate, cookies):
        return requests.post(
            f"{self.base_url}/api/reconductoring",
            json=data.model_dump(mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def update_reconductoring_event(self, event_id: int, update: ReconductoringUpdate, cookies):
        return requests.patch(
            f"{self.base_url}/api/reconductoring/{event_id}",
            json=update.model_dump(exclude_unset=True, mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def delete_reconductoring_event(self, event_id: int, cookies):
        return requests.delete(
            f"{self.base_url}/api/reconductoring/{event_id}", cookies=cookies, timeout=10
        )

    def get_historical_results(self):
        response = requests.get(f"{self.base_url}/api/historical", timeout=10)
        response.raise_for_status()
        return [HistoricalResultDetail.model_validate(item) for item in response.json()["items"]]

    def create_historical_result(self, data: HistoricalResultCreate, cookies):
        return requests.post(
            f"{self.base_url}/api/historical",
            json=data.model_dump(mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def update_historical_result(self, result_id: int, update: HistoricalResultUpdate, cookies):
        return requests.patch(
            f"{self.base_url}/api/historical/{result_id}",
            json=update.model_dump(exclude_unset=True, mode="json"),
            cookies=cookies,
            timeout=10,
        )

    def delete_historical_result(self, result_id: int, cookies):
        return requests.delete(
            f"{self.base_url}/api/historical/{result_id}", cookies=cookies, timeout=10
        )
