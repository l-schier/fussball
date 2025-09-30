import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, ForeignKey, DateTime, CheckConstraint, Integer, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Player(Base):
    __tablename__ = "player"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, index=True)
    active = Column(Boolean, default=True)


class Team(Base):
    __tablename__ = "team"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_player_1_id = Column(UUID(as_uuid=True), ForeignKey("player.id"), nullable=False)
    team_player_2_id = Column(UUID(as_uuid=True), ForeignKey("player.id"), nullable=True)


class Match(Base):
    __tablename__ = "match"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, nullable=False)
    winning_team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), nullable=False)
    losing_team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), nullable=False)
    winning_team_score = Column(Integer, nullable=False)
    losing_team_score = Column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("winning_team_score = 10", name="winning_team_score_check"),
        CheckConstraint("losing_team_score >= 0 AND losing_team_score != 10", name="losing_team_score_check"),
    )

class PlayerRating(Base):
    __tablename__ = "player_rating"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("match.id"), nullable=False)
    player_id = Column(UUID(as_uuid=True), ForeignKey("player.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


class TeamMatch(Base):
    __tablename__ = "team_match"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("team.id"), nullable=False)
    match_id = Column(UUID(as_uuid=True), ForeignKey("match.id"), nullable=False)


class TeamRating(Base):
    __tablename__ = "team_rating"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_match_id = Column(UUID(as_uuid=True), ForeignKey("team_match.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
