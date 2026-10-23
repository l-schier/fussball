from dataclasses import dataclass
from datetime import UTC
from uuid import UUID

from database.tables import Match, Player, Team, TeamMatch
from elo.elo_calculator import get_or_create_team
from elo.match_errors import MatchNotFoundError
from elo.rating_replay import replay_rating_history
from elo.upload_match import MatchCorrection
from sqlalchemy import select
from sqlalchemy.orm import Session


class InvalidPlayerSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class MatchCorrectionChanges:
    lineup_changed: bool
    played_at_changed: bool


def correct_match_scores(con: Session, match_id: UUID, correction: MatchCorrection) -> MatchCorrectionChanges:
    """Correct scores, participants, or played-at time and rebuild ratings atomically."""
    with con.begin():
        match = con.get(Match, match_id)
        if match is None:
            raise MatchNotFoundError(str(match_id))

        team_1_id = match.winning_team_id
        team_2_id = match.losing_team_id
        team_1 = con.get(Team, team_1_id)
        team_2 = con.get(Team, team_2_id)
        if team_1 is None or team_2 is None:
            raise MatchNotFoundError(str(match_id))

        current_player_ids = {
            player_id
            for player_id in (
                team_1.team_player_1_id,
                team_1.team_player_2_id,
                team_2.team_player_1_id,
                team_2.team_player_2_id,
            )
            if player_id is not None
        }
        fields_set = correction.model_fields_set
        team_1_players = _edited_lineup(
            correction,
            fields_set,
            team_1,
            "player_1",
            "player_2",
        )
        team_2_players = _edited_lineup(
            correction,
            fields_set,
            team_2,
            "player_3",
            "player_4",
        )
        _validate_player_selections(con, (*team_1_players, *team_2_players), current_player_ids)

        replacement_team_1 = get_or_create_team(*team_1_players, con)
        replacement_team_2 = get_or_create_team(*team_2_players, con)
        con.flush()

        team_matches = con.execute(select(TeamMatch).where(TeamMatch.match_id == match_id)).scalars().all()
        team_match_1 = next((row for row in team_matches if row.team_id == team_1_id), None)
        team_match_2 = next((row for row in team_matches if row is not team_match_1 and row.team_id == team_2_id), None)
        if team_match_1 is None or team_match_2 is None:
            raise MatchNotFoundError(str(match_id))
        played_at_changed = False
        if correction.date is not None:
            played_at = correction.date
            if played_at.tzinfo is not None:
                played_at = played_at.astimezone(UTC).replace(tzinfo=None)
            played_at_changed = played_at != match.created_at
            if played_at_changed:
                match.created_at = played_at
                team_match_1.created_at = played_at
                team_match_2.created_at = played_at

        team_match_1.team_id = replacement_team_1.id
        team_match_2.team_id = replacement_team_2.id

        if correction.score_team_1 > correction.score_team_2:
            match.winning_team_id = replacement_team_1.id
            match.losing_team_id = replacement_team_2.id
            match.winning_team_score = correction.score_team_1
            match.losing_team_score = correction.score_team_2
        else:
            match.winning_team_id = replacement_team_2.id
            match.losing_team_id = replacement_team_1.id
            match.winning_team_score = correction.score_team_2
            match.losing_team_score = correction.score_team_1

        lineup_changed = replacement_team_1.id != team_1_id or replacement_team_2.id != team_2_id
        replay_rating_history(con)

    return MatchCorrectionChanges(lineup_changed, played_at_changed)


def _edited_lineup(
    correction: MatchCorrection,
    fields_set: set[str],
    current_team: Team,
    player_1_field: str,
    player_2_field: str,
) -> tuple[UUID, UUID | None]:
    player_1_id = getattr(correction, player_1_field) if player_1_field in fields_set else current_team.team_player_1_id
    player_2_id = getattr(correction, player_2_field) if player_2_field in fields_set else current_team.team_player_2_id
    if player_1_id is None and player_2_id is not None:
        player_1_id, player_2_id = player_2_id, None
    if player_1_id is None:
        raise InvalidPlayerSelectionError("Each team must include at least one player")
    return player_1_id, player_2_id


def _validate_player_selections(
    con: Session,
    selected_player_ids: tuple[UUID | None, ...],
    current_player_ids: set[UUID],
) -> None:
    requested_ids = {player_id for player_id in selected_player_ids if player_id is not None}
    players = con.execute(select(Player).where(Player.id.in_(requested_ids))).scalars().all()
    players_by_id = {player.id: player for player in players}
    if requested_ids - players_by_id.keys():
        raise InvalidPlayerSelectionError("A selected player does not exist")

    unavailable_ids = {
        player_id
        for player_id, player in players_by_id.items()
        if not player.active and player_id not in current_player_ids
    }
    if unavailable_ids:
        raise InvalidPlayerSelectionError("Inactive players can only remain in their existing match")
