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
            # wt.team_player_1_id.label("team1_player1_id"),
            # wt.team_player_2_id.label("team1_player2_id"),
            # lt.team_player_1_id.label("team2_player1_id"),
            # lt.team_player_2_id.label("team2_player2_id"),
        )
        .join(wt, Match.winning_team_id == wt.id)
        .join(lt, Match.losing_team_id == lt.id)
        .outerjoin(p1, wt.team_player_1_id == p1.id)
        .outerjoin(p2, wt.team_player_2_id == p2.id)
        .outerjoin(p3, lt.team_player_1_id == p3.id)
        .outerjoin(p4, lt.team_player_2_id == p4.id)
        .where(Match.id == match_id)
        .limit(1)
    )
    result = con.execute(stmt)
    out = result.fetchone()
    return MatchDetails(*out)

def get_player_ratings_after_match(con: Session, match_id: UUID) -> list[PlayerRatingInfo]:
    # Get the last match
        # Get the last match
    wt = aliased(Team, name="wt")
    lt = aliased(Team, name="lt")

    last_match = (
        select(
            Match.id.label("match_id"),
            Match.created_at.label("match_time"),
            wt.team_player_1_id.label("player1_id"),
            wt.team_player_2_id.label("player2_id"),
            lt.team_player_1_id.label("player3_id"),
            lt.team_player_2_id.label("player4_id"),
        )
        .join(wt, Match.winning_team_id == wt.id)
        .join(lt, Match.losing_team_id == lt.id)
        .where(Match.id == match_id)
        .order_by(Match.id.desc())
        .limit(1)
        .cte("last_match")
    )

    # union of the four player id columns from last_match
    players_union = union_all(
        select(last_match.c.player1_id.label("player_id")),
        select(last_match.c.player2_id.label("player_id")),
        select(last_match.c.player3_id.label("player_id")),
        select(last_match.c.player4_id.label("player_id")),
    ).subquery()

    pm = aliased(PlayerMatch, name="pm")
    pr = aliased(PlayerRating, name="pr")

    player_ratings = (
        select(
            pm.player_id.label("player_id"),
            pr.rating.label("rating"),
            pr.created_at.label("created_at"),
            func.row_number()
            .over(partition_by=pm.player_id, order_by=pr.created_at.desc())
            .label("rn"),
        )
        .join(pr, pr.player_match_id == pm.id)
        .where(pm.player_id.in_(select(players_union.c.player_id)))
        .cte("player_ratings")
    )

    pr_before = player_ratings.alias("pr_before")
    pr_after = player_ratings.alias("pr_after")

    p = aliased(Player, name="p")

    final_stmt = (
        select(
            p.id.label("player_id"),
            p.name,
            pr_before.c.rating.label("rating_before"),
            pr_after.c.rating.label("rating_after"),
        )
        .select_from(p)
        .outerjoin(pr_before, (p.id == pr_before.c.player_id) & (pr_before.c.rn == 2))
        .outerjoin(pr_after, (p.id == pr_after.c.player_id) & (pr_after.c.rn == 1))
        .where(p.id.in_(select(players_union.c.player_id)))
        .order_by(p.id)
    )

    result = con.execute(final_stmt)
    rows = result.fetchall()
    return [PlayerRatingInfo.model_validate({**r._mapping}) for r in rows]