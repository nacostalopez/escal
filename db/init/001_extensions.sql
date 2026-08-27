-- TimescaleDB + UUID generation
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid()
