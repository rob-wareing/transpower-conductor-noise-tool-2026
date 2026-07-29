from transpower_conductor_noise_tool_2026.backend.persistence.models.historical_result import (
    HistoricalResult,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.historical_result_repository import (
    HistoricalResultRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    HistoricalResultCreate,
    HistoricalResultDetail,
    HistoricalResultUpdate,
)


def list_historical_results(
    repository: HistoricalResultRepository | None = None,
) -> list[HistoricalResultDetail]:
    repository = repository or HistoricalResultRepository()
    return [HistoricalResultDetail.model_validate(result) for result in repository.list_results()]


def create_historical_result(
    data: HistoricalResultCreate, repository: HistoricalResultRepository | None = None
) -> HistoricalResult:
    repository = repository or HistoricalResultRepository()
    result = HistoricalResult(**data.model_dump())
    return repository.add(result)


def update_historical_result(
    result_id: int,
    update: HistoricalResultUpdate,
    repository: HistoricalResultRepository | None = None,
):
    repository = repository or HistoricalResultRepository()
    result = repository.find_by_id(result_id)
    if result is None:
        return None

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(result, field, value)

    return repository.save(result)


def delete_historical_result(
    result_id: int, repository: HistoricalResultRepository | None = None
) -> bool:
    repository = repository or HistoricalResultRepository()
    result = repository.find_by_id(result_id)
    if result is None:
        return False

    repository.delete(result)
    return True
