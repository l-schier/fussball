page_routes = {
    "Home": "/",
    "Matches": "/match",
    "Players": "/player",
}

routes = {
    "player_detail": "/player/{player_id}",
    "match_detail": "/match/{match_id}",
    **page_routes,
}
