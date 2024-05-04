SET max_parallel_maintenance_workers TO 80;
SET maintenance_work_mem TO '16 GB';

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    age INTEGER
);

CREATE TABLE urls (
    id_urls BIGSERIAL PRIMARY KEY,
    url TEXT UNIQUE
);

create table messages (
    id BIGSERIAL primary key,
    sender_id integer not null REFERENCES users(id),
    message text not null,
    created_at timestamp not null default current_timestamp,
    id_urls INTEGER REFERENCES urls(id_urls)
);

CREATE TABLE fts_word(
	word text PRIMARY KEY
);

CREATE EXTENSION IF NOT EXISTS RUM;
CRATE EXTESNION IF NOT EXISTS pg_trgm;

CREATE INDEX retrieve_messages ON messages(created_at, id, sender_id, message);
CREATE INDEX query_messages ON messages USING RUM (to_tsvector('english', message));
