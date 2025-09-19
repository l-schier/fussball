from sqlalchemy import select, func, desc, union_all, over
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from fussball.database.tables import Player, PlayerMatch, PlayerRating, Match, Team
from fussball.database.dto import PlayerRatingInfo

async def get_last_match_player_ratings_query(con: AsyncSession):
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
        .order_by(desc(Match.id))
        .limit(1)
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

    result = await con.execute(query)
    rows = result.fetchall()

    # Convert rows to class instances
    return [PlayerRatingInfo(*row) for row in rows]