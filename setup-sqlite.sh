#!/bin/bash
# Script to set up the database
uv run sqlite3 ./data/database.db "VACUUM;"

# apply migrations
uv run alembic upgrade head

# Create a schema migration
# uv run alembic revision --autogenerate -m "<change description>"