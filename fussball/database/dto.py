from datetime import datetime
from uuid import UUID
from pydantic.dataclasses import dataclass

@dataclass
class PlayerRatingInfo:
    player_id: UUID
    name: str
    rating_before: int | None
    rating_after: int | None

@dataclass
class MatchDetails:
    matchid: UUID
    created_at: datetime
    player1_name: str
    player2_name: str | None
    player3_name: str
    player4_name: str | None
    team1_score: int
    team2_score: int