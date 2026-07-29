from transpower_conductor_noise_tool_2026.backend.persistence.models.reconductoring import (
    Reconductoring,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.reconductoring_repository import (
    ReconductoringRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    ReconductoringCreate,
    ReconductoringDetail,
    ReconductoringUpdate,
)


def list_reconductoring_events(
    repository: ReconductoringRepository | None = None,
) -> list[ReconductoringDetail]:
    repository = repository or ReconductoringRepository()
    return [ReconductoringDetail.model_validate(event) for event in repository.list_events()]


def create_reconductoring_event(
    data: ReconductoringCreate, repository: ReconductoringRepository | None = None
) -> Reconductoring:
    repository = repository or ReconductoringRepository()
    event = Reconductoring(**data.model_dump())
    return repository.add(event)


def update_reconductoring_event(
    event_id: int,
    update: ReconductoringUpdate,
    repository: ReconductoringRepository | None = None,
):
    repository = repository or ReconductoringRepository()
    event = repository.find_by_id(event_id)
    if event is None:
        return None

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    return repository.save(event)


def delete_reconductoring_event(
    event_id: int, repository: ReconductoringRepository | None = None
) -> bool:
    repository = repository or ReconductoringRepository()
    event = repository.find_by_id(event_id)
    if event is None:
        return False

    repository.delete(event)
    return True
