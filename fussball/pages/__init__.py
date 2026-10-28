page_routes = {
    "Home": "/",
    "Matches": "/match",
    "Players": "/player",
    "Team Rankings": "/team",
}

routes = {
    "player_detail": "/player/{player_id}",
    "team_detail": "/team/{team_id}",
    "team_match_history": "/team/{team_id}/matches/{page}",
    "player_ratings": "/player/{player_id}/ratings/{page}",
    "match_detail": "/match/{match_id}",
    "match_edit": "/match/{match_id}/edit",
    "match_remove": "/match/{match_id}/remove",
    **page_routes,
}
