-- Development contract slice. JSONB snapshots retain the shared model shape.
-- Cross-resource evidence semantics are validated by Bundle before seeding.
CREATE TABLE tenants (
    id text PRIMARY KEY,
    data jsonb NOT NULL CHECK (data->>'id' = id)
);
CREATE TABLE users (
    tenant_id text NOT NULL REFERENCES tenants(id), id text NOT NULL,
    data jsonb NOT NULL,
    app_role text GENERATED ALWAYS AS (data->>'app_role') STORED,
    PRIMARY KEY (tenant_id, id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (app_role IN ('candidate','recruiter','operator'))
);
CREATE TABLE campaigns (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    version integer GENERATED ALWAYS AS ((data->>'version')::integer) STORED,
    approved_by text GENERATED ALWAYS AS (data->>'approved_by') STORED,
    status text GENERATED ALWAYS AS (data->>'status') STORED,
    PRIMARY KEY (tenant_id, id), UNIQUE (tenant_id, id, version),
    FOREIGN KEY (tenant_id, approved_by) REFERENCES users(tenant_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (version > 0 AND status IN ('draft','proposed','approved')),
    CHECK (status <> 'approved' OR (approved_by IS NOT NULL AND data->>'approved_at' IS NOT NULL))
);
CREATE TABLE rooms (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    candidate_id text GENERATED ALWAYS AS (data->>'candidate_id') STORED NOT NULL,
    campaign_id text GENERATED ALWAYS AS (data->>'campaign_id') STORED NOT NULL,
    campaign_version integer GENERATED ALWAYS AS ((data->>'campaign_version')::integer) STORED NOT NULL,
    status text GENERATED ALWAYS AS (data->>'status') STORED NOT NULL,
    PRIMARY KEY (tenant_id,id),
    FOREIGN KEY (tenant_id,candidate_id) REFERENCES users(tenant_id,id),
    FOREIGN KEY (tenant_id,campaign_id,campaign_version) REFERENCES campaigns(tenant_id,id,version),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (status IN ('draft','published','revoked','completed')),
    CHECK (status = 'draft' OR data->>'published_at' IS NOT NULL),
    CHECK (status = 'draft' OR data->'cv_attachment' = 'null'::jsonb OR data->'cv_attachment'->>'scan_status' = 'available')
);
CREATE TABLE sessions (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    room_id text GENERATED ALWAYS AS (data->>'room_id') STORED NOT NULL,
    status text GENERATED ALWAYS AS (data->>'status') STORED NOT NULL,
    input_version integer GENERATED ALWAYS AS ((data->>'input_version')::integer) STORED NOT NULL,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,room_id),
    FOREIGN KEY (tenant_id,room_id) REFERENCES rooms(tenant_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (status IN ('active','interrupted','ended') AND input_version > 0),
    CHECK (data->>'started_at' IS NULL OR data->'consent'->>'choice' = 'true'),
    CHECK ((status = 'ended') = (data->>'ended_at' IS NOT NULL AND data->>'end_reason' IS NOT NULL))
);
CREATE TABLE turns (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    event_id text GENERATED ALWAYS AS (data->>'event_id') STORED NOT NULL,
    sequence integer GENERATED ALWAYS AS ((data->>'sequence')::integer) STORED NOT NULL,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,id),
    UNIQUE (tenant_id,session_id,event_id), UNIQUE (tenant_id,session_id,sequence),
    FOREIGN KEY (tenant_id,session_id) REFERENCES sessions(tenant_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (sequence > 0 AND length(data->>'finalized_text') BETWEEN 1 AND 4000),
    CHECK ((data->>'speaker' = 'candidate' AND data->>'delivery_status' = 'stt_final') OR
           (data->>'speaker' = 'assistant' AND data->>'delivery_status' IN ('confirmed_delivered','partial')))
);
CREATE TABLE corrections (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    target_turn_id text GENERATED ALWAYS AS (data->>'target_turn_id') STORED NOT NULL,
    replacement_turn_id text GENERATED ALWAYS AS (data->>'replacement_turn_id') STORED NOT NULL,
    input_version integer GENERATED ALWAYS AS ((data->>'input_version')::integer) STORED NOT NULL,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,target_turn_id,input_version),
    FOREIGN KEY (tenant_id,session_id,target_turn_id) REFERENCES turns(tenant_id,session_id,id),
    FOREIGN KEY (tenant_id,session_id,replacement_turn_id) REFERENCES turns(tenant_id,session_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (target_turn_id <> replacement_turn_id AND input_version > 1)
);
CREATE TABLE questions (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    turn_id text GENERATED ALWAYS AS (data->>'turn_id') STORED NOT NULL,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,id),
    FOREIGN KEY (tenant_id,session_id,turn_id) REFERENCES turns(tenant_id,session_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id)
);
CREATE TABLE answers (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    question_id text GENERATED ALWAYS AS (data->>'question_id') STORED NOT NULL,
    confirmed_answer_turn_id text GENERATED ALWAYS AS (data->>'confirmed_answer_turn_id') STORED,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,question_id),
    FOREIGN KEY (tenant_id,session_id,question_id) REFERENCES questions(tenant_id,session_id,id),
    FOREIGN KEY (tenant_id,session_id,confirmed_answer_turn_id) REFERENCES turns(tenant_id,session_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (data->>'status' IN ('answered','unknown','conflict','expired'))
);
CREATE TABLE jobs (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    input_version integer GENERATED ALWAYS AS ((data->>'input_version')::integer) STORED NOT NULL,
    status text GENERATED ALWAYS AS (data->>'status') STORED NOT NULL,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,input_version),
    FOREIGN KEY (tenant_id,session_id) REFERENCES sessions(tenant_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (status IN ('pending','processing','done','failed') AND input_version > 0),
    CHECK ((data->>'attempts')::integer BETWEEN 0 AND 3),
    CHECK ((status = 'processing') = (data->>'lease_until' IS NOT NULL))
);
CREATE TABLE reports (
    tenant_id text NOT NULL, id text NOT NULL, data jsonb NOT NULL,
    session_id text GENERATED ALWAYS AS (data->>'session_id') STORED NOT NULL,
    input_version integer GENERATED ALWAYS AS ((data->>'input_version')::integer) STORED NOT NULL,
    report_version integer GENERATED ALWAYS AS ((data->>'report_version')::integer) STORED NOT NULL,
    reviewer_id text GENERATED ALWAYS AS (data->>'reviewer_id') STORED,
    PRIMARY KEY (tenant_id,id), UNIQUE (tenant_id,session_id,input_version),
    UNIQUE (tenant_id,session_id,report_version),
    FOREIGN KEY (tenant_id,session_id,input_version) REFERENCES jobs(tenant_id,session_id,input_version),
    FOREIGN KEY (tenant_id,reviewer_id) REFERENCES users(tenant_id,id),
    CHECK (data->>'id' = id AND data->>'tenant_id' = tenant_id),
    CHECK (report_version > 0 AND data->>'status' IN ('draft','reviewed','superseded')),
    CHECK (data->>'status' <> 'reviewed' OR (reviewer_id IS NOT NULL AND data->>'reviewed_at' IS NOT NULL)),
    CHECK (data->>'status' <> 'draft' OR (reviewer_id IS NULL AND data->>'reviewed_at' IS NULL))
);

CREATE FUNCTION protect_contract_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME IN ('turns','corrections') THEN
        RAISE EXCEPTION 'append-only transcript history';
    END IF;
    IF TG_TABLE_NAME = 'campaigns' AND OLD.data->>'status' = 'approved' AND NEW.data IS DISTINCT FROM OLD.data THEN
        RAISE EXCEPTION 'approved snapshot is immutable; create new ID/version';
    END IF;
    IF TG_TABLE_NAME = 'rooms' AND OLD.data->>'published_at' IS NOT NULL THEN
        IF (NEW.data - 'status') IS DISTINCT FROM (OLD.data - 'status') THEN
            RAISE EXCEPTION 'published room binding is immutable including CV absence';
        END IF;
        IF NEW.data->>'status' NOT IN ('revoked','completed') AND NEW.data->>'status' IS DISTINCT FROM OLD.data->>'status' THEN
            RAISE EXCEPTION 'published room cannot return to draft';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER campaign_history BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
CREATE TRIGGER room_history BEFORE UPDATE ON rooms FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
-- Ordinary writes cannot erase history. Authorized retention/purge needs a future
-- deliberate policy implementation; these guards do not promise indefinite retention.
CREATE TRIGGER turn_history BEFORE UPDATE OR DELETE ON turns FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
CREATE TRIGGER correction_history BEFORE UPDATE OR DELETE ON corrections FOR EACH ROW EXECUTE FUNCTION protect_contract_history();
