-- Additive migration: never change the recorded checksum of 002_auth.sql.
ALTER TABLE auth_flows DROP CONSTRAINT auth_flows_return_to_check;
ALTER TABLE auth_flows ADD CONSTRAINT auth_flows_return_to_check CHECK (
    return_to ~ '^(/|/roles|/hr|/admin|/rooms/[A-Za-z0-9_-]{3,80}|/sessions/[A-Za-z0-9_-]{3,80}/interview)$'
    AND return_to !~ '[[:space:]]'
);

-- Grants are provisioned by an authorized operator, never by OAuth or a candidate.
-- HR scope is an exact campaign; Admin never implies HR or content access.
CREATE TABLE web_access_grants (
    id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES auth_accounts(id),
    permission text NOT NULL CHECK (permission IN ('hr','admin')),
    campaign_id text,
    granted_by uuid NOT NULL REFERENCES auth_accounts(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    confirmed_at timestamptz,
    revoked_at timestamptz,
    CHECK ((permission='hr' AND campaign_id IS NOT NULL) OR (permission='admin' AND campaign_id IS NULL))
);

-- Persisted synthetic preparation only. No approved hiring notice or live media.
-- Assignment is to the verified account ID, not a transferable URL capability.
CREATE TABLE web_room_previews (
    id text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9_-]{3,80}$'),
    candidate_id uuid NOT NULL REFERENCES auth_accounts(id),
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    role_id text NOT NULL CHECK (role_id IN ('ba','devops','fullstack','frontend','backend','ai')),
    opens_at timestamptz NOT NULL,
    closes_at timestamptz NOT NULL,
    timezone text NOT NULL,
    contact text NOT NULL,
    revoked_at timestamptz,
    CHECK (closes_at > opens_at)
);
CREATE INDEX web_room_candidate ON web_room_previews(candidate_id);
CREATE TABLE web_session_previews (
    id text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9_-]{3,80}$'),
    room_id text NOT NULL UNIQUE REFERENCES web_room_previews(id),
    acknowledged_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz
);

-- Never rebind a shared URL or existing session to a different account/campaign.
-- Incorrect assignments are revoked and replaced with a new room ID.
CREATE FUNCTION protect_web_room_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'revoked_at') IS DISTINCT FROM (to_jsonb(OLD) - 'revoked_at')
       OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at) THEN
        RAISE EXCEPTION 'room binding is immutable; revoke and create a new room';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER web_room_binding BEFORE UPDATE ON web_room_previews
    FOR EACH ROW EXECUTE FUNCTION protect_web_room_binding();
