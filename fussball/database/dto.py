from datetime import datetime
from uuid import UUID
from pydantic.dataclasses import dataclass
from pydantic import BaseModel


class PlayerRatingInfo(BaseModel):
    player_id: UUID
    name: str
    rating_before: int | None
    rating_after: int | None


class PlayerWithRating(BaseModel):
    id: UUID
    name: str
    ranking: int | None
    history: list[dict] = []


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


class MatchSummary(BaseModel):
    matchid: UUID
    created_at: datetime
    winning_team_score: int
    losing_team_score: int
    winning_team_id: UUID
    losing_team_id: UUID
