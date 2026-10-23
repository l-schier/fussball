from collections import defaultdict
from uuid import UUID, uuid4

from database.tables import Match, PlayerRating, Team, TeamMatch, TeamRating
from elo.elo_calculator import calculate_rating_player, calculate_rating_team, expected_score
from elo.upload_match import MatchScores
from sqlalchemy import delete, select
from sqlalchemy.orm import Session


def replay_rating_history(con: Session) -> None:
    """Rebuild derived ratings in played-at order, breaking ties by match UUID."""
    matches = con.execute(select(Match).order_by(Match.created_at, Match.id)).scalars().all()
    if not matches:
        con.execute(delete(PlayerRating))
        con.execute(delete(TeamRating))
        return

    teams = {team.id: team for team in con.execute(select(Team)).scalars()}
    team_matches = con.execute(select(TeamMatch)).scalars().all()
    team_match_ids = {(row.match_id, row.team_id): row.id for row in team_matches}

    player_ratings: dict[UUID, int] = defaultdict(lambda: 1500)
    team_ratings: dict[UUID, float] = defaultdict(lambda: 1500)
    player_games: dict[UUID, int] = defaultdict(int)
    team_games: dict[UUID, int] = defaultdict(int)
    new_player_ratings: list[PlayerRating] = []
    new_team_ratings: list[TeamRating] = []

    for match in matches:
        winning_team = teams[match.winning_team_id]
        losing_team = teams[match.losing_team_id]
        winning_players = [winning_team.team_player_1_id]
        losing_players = [losing_team.team_player_1_id]
        if winning_team.team_player_2_id is not None:
            winning_players.append(winning_team.team_player_2_id)
        if losing_team.team_player_2_id is not None:
            losing_players.append(losing_team.team_player_2_id)

        scores = MatchScores(
            score_team_1=match.winning_team_score,
            score_team_2=match.losing_team_score,
        )
        winning_opponent_ratings = [player_ratings[player_id] for player_id in losing_players]
        losing_opponent_ratings = [player_ratings[player_id] for player_id in winning_players]
        winning_expected = {
            player_id: expected_score(player_ratings[player_id], winning_opponent_ratings)
            for player_id in winning_players
        }
        losing_expected = {
            player_id: expected_score(player_ratings[player_id], losing_opponent_ratings)
            for player_id in losing_players
        }

        for player_id in winning_players:
            player_ratings[player_id] = calculate_rating_player(
                player_games[player_id], scores, player_ratings[player_id], winning_expected[player_id], 1
            )
            player_games[player_id] += 1
            new_player_ratings.append(
                PlayerRating(
                    id=uuid4(),
                    match_id=match.id,
                    player_id=player_id,
                    rating=player_ratings[player_id],
                    created_at=match.created_at,
                )
            )

        for player_id in losing_players:
            player_ratings[player_id] = calculate_rating_player(
                player_games[player_id], scores, player_ratings[player_id], losing_expected[player_id], 0
            )
            player_games[player_id] += 1
            new_player_ratings.append(
                PlayerRating(
                    id=uuid4(),
                    match_id=match.id,
                    player_id=player_id,
                    rating=player_ratings[player_id],
                    created_at=match.created_at,
                )
            )

        winning_expected_score = sum(winning_expected.values()) / len(winning_players)
        losing_expected_score = sum(losing_expected.values()) / len(losing_players)
        # Team K-factor counts the match being rated, matching submission's existing behavior.
        winning_team_rating = calculate_rating_team(
            team_games[winning_team.id] + 1, scores, team_ratings[winning_team.id], winning_expected_score, 1
        )
        losing_team_rating = calculate_rating_team(
            team_games[losing_team.id] + 1, scores, team_ratings[losing_team.id], losing_expected_score, 0
        )
        team_ratings[winning_team.id] = winning_team_rating
        team_ratings[losing_team.id] = losing_team_rating
        team_games[winning_team.id] += 1
        team_games[losing_team.id] += 1

        new_team_ratings.extend(
            [
                TeamRating(
                    id=uuid4(),
                    team_match_id=team_match_ids[(match.id, winning_team.id)],
                    rating=winning_team_rating,
                    created_at=match.created_at,
                ),
                TeamRating(
                    id=uuid4(),
                    team_match_id=team_match_ids[(match.id, losing_team.id)],
                    rating=losing_team_rating,
                    created_at=match.created_at,
                ),
            ]
        )

    con.execute(delete(PlayerRating))
    con.execute(delete(TeamRating))
    con.add_all(new_player_ratings)
    con.add_all(new_team_ratings)
    con.flush()
