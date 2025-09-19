from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from uuid import UUID


class UploadMatch(BaseModel):
    player_1: UUID
    player_2: Optional[UUID] = None
    score_team_1: int = Field(ge=0, lt=11)

    player_3: UUID
    player_4: Optional[UUID] = None
    score_team_2: int = Field(ge=0, lt=11)

    date: datetime
