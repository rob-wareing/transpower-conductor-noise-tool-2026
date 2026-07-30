from transpower_conductor_noise_tool_2026.backend.persistence.repositories.processed_reading_repository import (
    ProcessedReadingRepository,
)
from transpower_conductor_noise_tool_2026.shared.contracts import ProcessedReadingUpdate


def update_processed_reading(
    reading_id: int,
    update: ProcessedReadingUpdate,
    repository: ProcessedReadingRepository | None = None,
):
    repository = repository or ProcessedReadingRepository()
    reading = repository.find_by_id(reading_id)
    if reading is None:
        return None

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(reading, field, value)

    return repository.save(reading)
