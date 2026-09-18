"""内置迁移。"""

SCHEMA_VERSION = 5

INITIAL_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspace_meta (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  schema_version INTEGER NOT NULL,
  project_version TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_migrated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
  idempotency_key TEXT PRIMARY KEY,
  input_hash TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_imports (
  raw_import_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  source_hash TEXT NOT NULL UNIQUE,
  schema_name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  markets TEXT NOT NULL,
  segments TEXT NOT NULL,
  target_count INTEGER NOT NULL CHECK (target_count > 0),
  candidate_pool_multiplier REAL NOT NULL DEFAULT 3.0 CHECK (candidate_pool_multiplier >= 1.0),
  min_source_categories INTEGER NOT NULL DEFAULT 3 CHECK (min_source_categories >= 1),
  production_min_target INTEGER NOT NULL DEFAULT 20 CHECK (production_min_target >= 1),
  status TEXT NOT NULL,
  next_action TEXT NOT NULL DEFAULT '',
  product_version TEXT NOT NULL DEFAULT '',
  voice_version TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE TABLE IF NOT EXISTS companies (
  company_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(run_id),
  name_original TEXT NOT NULL,
  name_normalized TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  segment TEXT NOT NULL DEFAULT '',
  website TEXT NOT NULL DEFAULT '',
  root_domain TEXT NOT NULL DEFAULT '',
  linkedin_url TEXT NOT NULL DEFAULT '',
  fit_status TEXT NOT NULL DEFAULT 'chat_candidate',
  fit_reason TEXT NOT NULL DEFAULT '',
  risk_notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_company_run_domain ON companies(run_id, root_domain) WHERE root_domain <> '';
CREATE TABLE IF NOT EXISTS contacts (
  contact_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  full_name TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  role_scope TEXT NOT NULL DEFAULT '',
  contact_role TEXT NOT NULL DEFAULT 'primary',
  linkedin_url TEXT NOT NULL DEFAULT '',
  public_email TEXT NOT NULL DEFAULT '',
  identity_status TEXT NOT NULL DEFAULT 'unverified',
  contact_status TEXT NOT NULL DEFAULT 'not_contacted',
  last_verified_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_company_linkedin ON contacts(company_id,linkedin_url) WHERE linkedin_url <> '';
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_company_email ON contacts(company_id,public_email) WHERE public_email <> '';
CREATE TABLE IF NOT EXISTS entity_keys (
  entity_key_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  key_type TEXT NOT NULL,
  normalized_value TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  source TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_entity_key ON entity_keys(entity_type,entity_id,key_type,normalized_value)
WHERE status='active';
CREATE TABLE IF NOT EXISTS source_runs (
  source_run_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(run_id),
  adapter_id TEXT NOT NULL,
  query_summary TEXT NOT NULL DEFAULT '',
  query_fingerprint TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 1,
  outcome TEXT NOT NULL,
  result_count INTEGER NOT NULL DEFAULT 0,
  cost_amount REAL NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  error_code TEXT NOT NULL DEFAULT '',
  retryable INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS source_plan_entries (
  source_plan_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  source_category TEXT NOT NULL,
  source_role TEXT NOT NULL DEFAULT 'discover',
  target_signal TEXT NOT NULL DEFAULT '',
  query_or_entry_url TEXT NOT NULL,
  coverage TEXT NOT NULL DEFAULT '',
  access_status TEXT NOT NULL DEFAULT 'planned',
  contribution TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(run_id, source_category, query_or_entry_url)
);
CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  name_original TEXT NOT NULL,
  name_normalized TEXT NOT NULL,
  root_domain TEXT NOT NULL DEFAULT '',
  primary_source_url TEXT NOT NULL,
  country_hint TEXT NOT NULL DEFAULT '',
  segment_hint TEXT NOT NULL DEFAULT '',
  discovery_status TEXT NOT NULL DEFAULT 'candidate_pool',
  decision_reason TEXT NOT NULL DEFAULT '',
  selected_company_id TEXT REFERENCES companies(company_id),
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  UNIQUE(run_id, name_normalized)
);
CREATE TABLE IF NOT EXISTS candidate_sources (
  candidate_source_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
  source_run_id TEXT NOT NULL REFERENCES source_runs(source_run_id),
  source_category TEXT NOT NULL,
  source_url TEXT NOT NULL,
  observed_text TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  UNIQUE(candidate_id, source_url)
);
CREATE INDEX IF NOT EXISTS ix_candidates_run_status ON candidates(run_id, discovery_status);
CREATE INDEX IF NOT EXISTS ix_candidate_sources_run ON candidate_sources(run_id, source_category);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  source_run_id TEXT REFERENCES source_runs(source_run_id),
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_level TEXT NOT NULL DEFAULT 'secondary',
  purpose TEXT NOT NULL DEFAULT '',
  observed_text TEXT NOT NULL,
  published_at TEXT,
  observed_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  access_status TEXT NOT NULL DEFAULT 'accessible',
  conflicts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  proposed_value TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  evidence_grade TEXT NOT NULL DEFAULT 'unknown',
  conflict_reason TEXT NOT NULL DEFAULT '',
  decided_by TEXT,
  decided_at TEXT,
  decision_reason TEXT NOT NULL DEFAULT '',
  supersedes_claim_id TEXT REFERENCES claims(claim_id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id),
  evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
  PRIMARY KEY (claim_id, evidence_id)
);
CREATE TABLE IF NOT EXISTS research_gaps (
  gap_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  business_impact TEXT NOT NULL DEFAULT '',
  blocking INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS duplicate_candidates (
  duplicate_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  match_type TEXT NOT NULL,
  score REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  reviewed_by TEXT,
  reviewed_at TEXT,
  reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS drafts (
  draft_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(run_id),
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  contact_id TEXT NOT NULL REFERENCES contacts(contact_id),
  channel TEXT NOT NULL CHECK(channel IN ('email','linkedin')),
  subject TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL,
  evidence_ids TEXT NOT NULL DEFAULT '[]',
  product_version TEXT NOT NULL DEFAULT '',
  body_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT
);
CREATE TABLE IF NOT EXISTS draft_contracts (
  draft_id TEXT PRIMARY KEY REFERENCES drafts(draft_id),
  contract_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  -- body_hash字段兼容旧表；v4开始保存完整发送快照的哈希。
  approval_id TEXT PRIMARY KEY,
  draft_id TEXT NOT NULL REFERENCES drafts(draft_id),
  body_hash TEXT NOT NULL,
  approved_by TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS replies (
  reply_id TEXT PRIMARY KEY,
  external_message_id TEXT NOT NULL UNIQUE,
  contact_id TEXT NOT NULL REFERENCES contacts(contact_id),
  channel TEXT NOT NULL,
  received_at TEXT NOT NULL,
  source_reference TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL,
  confirmed_needs TEXT NOT NULL DEFAULT '',
  unknown_needs TEXT NOT NULL DEFAULT '',
  next_action TEXT NOT NULL DEFAULT '',
  needs_human_takeover INTEGER NOT NULL DEFAULT 0,
  do_not_contact INTEGER NOT NULL DEFAULT 0,
  raw_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stop_rules (
  stop_rule_id TEXT PRIMARY KEY,
  scope_type TEXT NOT NULL,
  scope_value TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  released_by TEXT,
  released_at TEXT,
  release_reason TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_stop ON stop_rules(scope_type, scope_value) WHERE status='active';
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL DEFAULT '',
  entity_id TEXT NOT NULL DEFAULT '',
  request_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(run_id, sequence)
);
"""
