from transpower_conductor_noise_tool_2026.backend.persistence.models.outage import Outage
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_repository import (
    OutageRepository,
)
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.outage_type_repository import (
    OutageTypeRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import (
    OutageCreate,
    OutageDetail,
    OutageUpdate,
)


def list_outages(repository: OutageRepository | None = None) -> list[OutageDetail]:
    repository = repository or OutageRepository()
    return [OutageDetail.model_validate(outage) for outage in repository.list_outages()]


def list_outage_types(repository: OutageTypeRepository | None = None) -> list[str]:
    repository = repository or OutageTypeRepository()
    return [outage_type.outage_type for outage_type in repository.list_types()]


def create_outage(data: OutageCreate, repository: OutageRepository | None = None) -> Outage:
    repository = repository or OutageRepository()
    outage = Outage(**data.model_dump())
    return repository.add(outage)


def update_outage(
    outage_id: int, update: OutageUpdate, repository: OutageRepository | None = None
):
    repository = repository or OutageRepository()
    outage = repository.find_by_id(outage_id)
    if outage is None:
        return None

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(outage, field, value)

    return repository.save(outage)


def delete_outage(outage_id: int, repository: OutageRepository | None = None) -> bool:
    repository = repository or OutageRepository()
    outage = repository.find_by_id(outage_id)
    if outage is None:
        return False

    repository.delete(outage)
    return True
