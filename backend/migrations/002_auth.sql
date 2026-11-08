-- Independent of contract/seed tables: no tenant privileges or email merging.
CREATE TABLE auth_accounts (
    id uuid PRIMARY KEY,
    issuer text NOT NULL,
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 255),
    email text NOT NULL,
    name text,
    role text NOT NULL DEFAULT 'candidate' CHECK (role = 'candidate'),
    UNIQUE (issuer, subject)
);
CREATE TABLE auth_flows (
    state_hash text PRIMARY KEY,
    browser_hash text NOT NULL,
    nonce text NOT NULL,
    verifier text NOT NULL,
    return_to text NOT NULL CHECK (return_to IN ('/', '/roles')),
    expires_at timestamptz NOT NULL
);
CREATE INDEX auth_flows_expiry ON auth_flows (expires_at);
CREATE TABLE auth_sessions (
    token_hash text PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES auth_accounts(id),
    expires_at timestamptz NOT NULL
);
CREATE INDEX auth_sessions_expiry ON auth_sessions (expires_at);
