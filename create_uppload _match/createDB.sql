CREATE TABLE IF NOT EXISTS Player (
    player_id serial PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS Team (
    team_id serial PRIMARY KEY,
    team_player_1_id INT NOT NULL REFERENCES Player(player_id),
    team_player_2_id INT NOT NULL REFERENCES Player(player_id)
);

CREATE TABLE IF NOT EXISTS MATCH (
    match_id serial PRIMARY KEY,
    match_timestamp TIMESTAMP NOT NULL,
    winning_team_id INT NOT NULL REFERENCES Team(team_id),
    losing_team_id INT NOT NULL REFERENCES Team(team_id),
    winning_team_score INT NOT NULL CHECK (winning_team_score = 11),
    losing_team_score INT NOT NULL CHECK (losing_team_score >= 0 AND losing_team_score != 11)
);

CREATE TABLE IF NOT EXISTS PlayerMatch (
    player_match_id serial PRIMARY KEY,
    player_id INT NOT NULL REFERENCES Player(player_id),
    match_id INT NOT NULL REFERENCES MATCH(match_id)
);

CREATE TABLE IF NOT EXISTS PlayerRating (
    player_rating_id serial PRIMARY KEY,
    player_match_id INT NOT NULL REFERENCES PlayerMatch(player_match_id),
    rating INT NOT NULL,
    player_rating_timestamp TIMESTAMP  NOT NULL
);

CREATE TABLE IF NOT EXISTS TeamMatch (
    team_match_id serial PRIMARY KEY,
    team_id INT NOT NULL REFERENCES Team(team_id),
    match_id INT NOT NULL REFERENCES MATCH(match_id)
);

CREATE TABLE IF NOT EXISTS TeamRating (
    team_rating_id serial PRIMARY KEY,
    team_match_id INT NOT NULL REFERENCES TeamMatch(team_match_id),
    rating INT NOT NULL,
    team_rating_timestamp TIMESTAMP  NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS player_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS team_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS match_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS player_match_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS player_rating_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS team_match_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS team_rating_id_seq START 1;