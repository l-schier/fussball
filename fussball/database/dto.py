from uuid import UUID
from pydantic.dataclasses import dataclass

@dataclass
class PlayerRatingInfo:
    player_id: UUID
    name: str
    rating_before: int | None
    rating_after: int | None