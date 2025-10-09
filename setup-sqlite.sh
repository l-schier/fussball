#!/bin/bash
# Script to set up the database
uv run sqlite3 ./data/database.db "VACUUM;"

# apply migrations
uv run alembic upgrade head