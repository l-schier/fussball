import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    CheckConstraint,
    Integer,
    Boolean,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import TypeDecorator, CHAR

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class Player(Base):
    __tablename__ = "player"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    name = Column(String, index=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)


class Team(Base):
    __tablename__ = "team"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    team_player_1_id = Column(GUID(), ForeignKey("player.id"), nullable=False)
    team_player_2_id = Column(GUID(), ForeignKey("player.id"), nullable=True)
    created_at = Column(DateTime, nullable=False)


class Match(Base):
    __tablename__ = "match"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    created_at = Column(DateTime, nullable=False, index=True)
    winning_team_id = Column(GUID(), ForeignKey("team.id"), index=True, nullable=False)
    losing_team_id = Column(GUID(), ForeignKey("team.id"), index=True, nullable=False)
    winning_team_score = Column(Integer, nullable=False)
    losing_team_score = Column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("winning_team_score = 10", name="winning_team_score_check"),
        CheckConstraint(
            "losing_team_score >= 0 AND losing_team_score != 10",
            name="losing_team_score_check",
        ),
    )


class PlayerRating(Base):
    __tablename__ = "player_rating"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    match_id = Column(GUID(), ForeignKey("match.id"), nullable=False)
    player_id = Column(GUID(), ForeignKey("player.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


class TeamMatch(Base):
    __tablename__ = "team_match"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    team_id = Column(GUID(), ForeignKey("team.id"), nullable=False)
    match_id = Column(GUID(), ForeignKey("match.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)


class TeamRating(Base):
    __tablename__ = "team_rating"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True, unique=True)
    team_match_id = Column(GUID(), ForeignKey("team_match.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)
