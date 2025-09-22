from uuid import UUID
from sqlalchemy import select, func, desc, union_all, over, text
from sqlalchemy.orm import aliased, Session
from fussball.database.tables import Player, PlayerMatch, PlayerRating, Match, Team
from fussball.database.dto import PlayerRatingInfo, MatchDetails

def get_match_details(con: Session, match_id: UUID) -> MatchDetails:
    wt = aliased(Team, name="wt")
    lt = aliased(Team, name="lt")
    p1 = aliased(Player, name="p1")
    p2 = aliased(Player, name="p2")
    p3 = aliased(Player, name="p3")
    p4 = aliased(Player, name="p4")


    stmt = (
        select(
            Match.id.label("matchid"),
            Match.created_at.label("created_at"),
            p1.name.label("player1_name"),
            p2.name.label("player2_name"),
            p3.name.label("player3_name"),
            p4.name.label("player4_name"),
            Match.winning_team_score.label("team1_score"),
            Match.losing_team_score.label("team2_score"),
            wt.team_player_1_id.label("team1_player1_id"),
            wt.team_player_2_id.label("team1_player2_id"),
            lt.team_player_1_id.label("team2_player1_id"),
            lt.team_player_2_id.label("team2_player2_id"),
        )
        .join(wt, Match.winning_team_id == wt.id)
        .join(lt, Match.losing_team_id == lt.id)
        .join(p1, wt.team_player_1_id == p1.id)
        .join(p2, wt.team_player_2_id == p2.id)
        .join(p3, lt.team_player_1_id == p3.id)
        .join(p4, lt.team_player_2_id == p4.id)
        .where(Match.id == match_id)
        .limit(1)
    )
    result = con.execute(stmt)
    out = result.fetchone()
    return MatchDetails(*out)

def get_player_ratings_after_match(con: Session, match_id: UUID) -> list[PlayerRatingInfo]:
    # Get the last match
    last_match_subq = (
        select(
            Match.id.label("match_id"),
            Match.created_at.label("match_time"),
            Team.team_player_1_id.label("player1_id"),
            Team.team_player_2_id.label("player2_id"),
            aliased(Team, name="lt").team_player_1_id.label("player3_id"),
            aliased(Team, name="lt").team_player_2_id.label("player4_id"),
        )
        .join(Team, Match.winning_team_id == Team.id)
        .join(aliased(Team, name="lt"), Match.losing_team_id == aliased(Team, name="lt").id)
        .where(Match.id == match_id)
        .subquery()
    )

    # Get all player IDs from last match
    player_ids_subq = union_all(
        select(last_match_subq.c.player1_id.label("player_id")),
        select(last_match_subq.c.player2_id.label("player_id")),
        select(last_match_subq.c.player3_id.label("player_id")),
        select(last_match_subq.c.player4_id.label("player_id")),
    ).subquery()

    player_ratings_subq = (
        select(
            PlayerMatch.player_id,
            PlayerRating.rating,
            PlayerRating.player_rating_timestamp,
            over(
                func.row_number(),
                partition_by=PlayerMatch.player_id,
                order_by=desc(PlayerRating.player_rating_timestamp)
            ).label("rn")
        )
        .join(PlayerMatch, PlayerRating.player_match_id == PlayerMatch.id)
        .where(PlayerMatch.player_id.in_(select(player_ids_subq.c.player_id)))
        .subquery()
    )

    pr_before = aliased(player_ratings_subq, name="pr_before")
    pr_after = aliased(player_ratings_subq, name="pr_after")

    # Final select
    query = (
        select(
            Player.id.label("player_id"),
            Player.name,
            pr_before.c.rating.label("rating_before"),
            pr_after.c.rating.label("rating_after"),
        )
        .outerjoin(pr_before, (Player.id == pr_before.c.player_id) & (pr_before.c.rn == 2))
        .outerjoin(pr_after, (Player.id == pr_after.c.player_id) & (pr_after.c.rn == 1))
        .where(Player.id.in_(select(player_ids_subq.c.player_id)))
        .order_by(Player.id)
    )

    result = con.execute(query)
    rows = result.fetchall()

    # Convert rows to class instances
    return [PlayerRatingInfo(*row) for row in rows]
