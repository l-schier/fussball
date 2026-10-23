from uuid import UUID

from database.tables import Match, PlayerRating, TeamMatch, TeamRating
from elo.match_errors import MatchNotFoundError
from elo.rating_replay import replay_rating_history
from sqlalchemy import delete, select
from sqlalchemy.orm import Session


def remove_match(con: Session, match_id: UUID) -> None:
    """Permanently remove a match and rebuild the derived rating history atomically."""
    with con.begin():
        match = con.get(Match, match_id)
        if match is None:
            raise MatchNotFoundError(str(match_id))

        team_match_ids = select(TeamMatch.id).where(TeamMatch.match_id == match_id)
        con.execute(delete(TeamRating).where(TeamRating.team_match_id.in_(team_match_ids)))
        con.execute(delete(PlayerRating).where(PlayerRating.match_id == match_id))
        con.execute(delete(TeamMatch).where(TeamMatch.match_id == match_id))
        con.execute(delete(Match).where(Match.id == match_id))

        replay_rating_history(con)
