-- Paper Radar database schema (Neon Postgres).
-- Safe to run more than once: every statement is IF NOT EXISTS.
-- Apply with:  DATABASE_URL_DIRECT=... python scripts/init_db.py

-- One account per member. Rows in every other table belong to exactly one user.
CREATE TABLE IF NOT EXISTS users (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    auth_sub       text NOT NULL UNIQUE,              -- Auth0 user id ("email|abc..."), set at first login
    email          text NOT NULL,
    name           text NOT NULL DEFAULT '',
    lab_name       text NOT NULL DEFAULT '',          -- free text, duplicates allowed, never used to share data
    email_enabled  boolean NOT NULL DEFAULT true,
    onboarded_at   timestamptz,                       -- null until the first-login form is finished
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (lower(email));

-- 2-3 keywords per user (the limit is enforced in core/db.py).
CREATE TABLE IF NOT EXISTS keywords (
    user_id    bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    position   smallint NOT NULL,
    term       text NOT NULL CHECK (length(btrim(term)) > 0),
    PRIMARY KEY (user_id, position)
);
CREATE UNIQUE INDEX IF NOT EXISTS keywords_user_term_key ON keywords (user_id, lower(term));

-- The OpenAlex profile the user confirmed (one per user for now; the key allows more later).
CREATE TABLE IF NOT EXISTS followed_authors (
    user_id       bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    openalex_id   text NOT NULL,                      -- short form, e.g. "A5023888391"
    display_name  text NOT NULL,
    institution   text NOT NULL DEFAULT '',
    confirmed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, openalex_id)
);

-- Weekly job runs (the run log).
CREATE TABLE IF NOT EXISTS runs (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'success', 'partial', 'failed')),
    trigger       text NOT NULL DEFAULT 'manual',     -- manual | schedule
    users_ok      integer NOT NULL DEFAULT 0,
    users_failed  integer NOT NULL DEFAULT 0,
    error         text
);

-- One report per user per week. Re-running the job for the same week replaces it.
CREATE TABLE IF NOT EXISTS reports (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start  date NOT NULL,                        -- Monday of the report week
    run_id      bigint REFERENCES runs(id) ON DELETE SET NULL,
    data        jsonb NOT NULL,                       -- everything the report page needs (papers, counts, trends)
    markdown    text NOT NULL DEFAULT '',
    email_html  text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    emailed_at  timestamptz,                          -- null until n8n has sent it
    UNIQUE (user_id, week_start)
);
CREATE INDEX IF NOT EXISTS reports_unsent_idx ON reports (week_start) WHERE emailed_at IS NULL;

-- Papers already shown to a user, so the same paper is never reported twice.
CREATE TABLE IF NOT EXISTS seen_papers (
    user_id          bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    work_id          text NOT NULL,                   -- short form, e.g. "W4391234567"
    first_seen_week  date NOT NULL,
    PRIMARY KEY (user_id, work_id)
);

-- Shared cache of public OpenAlex responses (not user data; same key format as core/openalex.py).
CREATE TABLE IF NOT EXISTS openalex_cache (
    cache_key  text PRIMARY KEY,
    data       jsonb NOT NULL,
    saved_at   timestamptz NOT NULL DEFAULT now()
);
