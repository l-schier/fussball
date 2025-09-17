

from datetime import datetime

from pydantic import BaseModel, Field


class UploadMatch(BaseModel):
    player_1: str
    player_2: str
    score_team_1: int = Field(ge=0, lt=11)
    
    player_3: str
    player_4: str
    score_team_2: int = Field(ge=0, lt=11)

    date: datetime