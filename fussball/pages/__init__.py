page_routes = {
    "Home": "/",
    "Matches": "/match",
    "Players": "/player",
}

routes = {
    "player_detail": "/player/{player_id}",
    "match_detail": "/match/{match_id}",
    "match_edit": "/match/{match_id}/edit",
    "match_remove": "/match/{match_id}/remove",
    **page_routes,
}
