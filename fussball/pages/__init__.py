
page_routes = {
    "index": "/",
    "match": "/match",
    "player": "/player",
}

routes = {
    "player_detail": "/player/{player_id}",
    "match_detail": "/match/{match_id}",
    **page_routes,
}