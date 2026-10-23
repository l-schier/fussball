from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator


def validate_match_scores(score_team_1: int, score_team_2: int) -> None:
    if score_team_1 == score_team_2:
        raise ValueError("A match cannot end in a draw")


class MatchScores(BaseModel):
    score_team_1: int = Field(ge=0, le=10)
    score_team_2: int = Field(ge=0, le=10)

    @field_validator("score_team_2")
    @classmethod
    def validate_result(cls, score_team_2: int, info: ValidationInfo) -> int:
        score_team_1 = info.data.get("score_team_1")
        if score_team_1 is not None:
            validate_match_scores(score_team_1, score_team_2)
        return score_team_2


class MatchCorrection(MatchScores):
    """Edit payload; played-at values are stored as naive UTC to match the database schema."""

    player_1: UUID | None = None
    player_2: UUID | None = None
    player_3: UUID | None = None
    player_4: UUID | None = None
    date: datetime | None = None

    @field_validator("player_1", "player_2", "player_3", "player_4", mode="before")
    @classmethod
    def empty_player_selection_is_none(cls, value):
        return None if value == "" else value


class UploadMatch(MatchScores):
    player_1: UUID
    player_2: UUID | None = None
    player_3: UUID
    player_4: UUID | None = None
    date: datetime


class UploadMatchOptional(MatchScores):
    player_1: UUID | None = None
    player_2: UUID | None = None
    player_3: UUID | None = None
    player_4: UUID | None = None
    date: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
