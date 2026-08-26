-- 034 — Consumer Search V2: term-level search over the imported title corpus.
--
-- Additive only. No occupation is created, no score is written, no publication state moves,
-- and `occupations.search_aliases` is left in place so a rollback is a code change rather
-- than a data restore.
--
-- ## Why this exists
--
-- V1 ranked by `similarity(o.title || ' ' || o.search_aliases, query)`. That blob averages
-- 1,269 characters and reaches 18,368. Trigram similarity divides shared trigrams by the
-- union, so a longer haystack means a larger denominator: the more alternate titles an
-- occupation carried, the *lower* it ranked. Measured on production, `data entry operator`
-- returned one row scoring 0.0254 — below the 0.18 threshold — admitted only because the
-- unanchored LIKE clause found all three tokens somewhere inside five kilobytes of text.
--
-- The fix is structural rather than a weight change: match against individual titles. The
-- 57,543 O*NET alternate titles already imported become 57,543 comparable candidates instead
-- of 1,016 undifferentiated blobs.
--
-- ## Why a materialised view and not a table
--
-- The terms are derived: canonical titles and O*NET alternate titles both already live in
-- this database, and duplicating 57k rows into a hand-maintained table would create a second
-- copy that drifts from the import. Only the curated consumer aliases are genuinely new
-- editorial data, and those get a real table because a human maintains them.
--
-- Publication status is deliberately NOT materialised. It changes when an occupation is
-- promoted, and a stale view that thinks a staged occupation is public would route a user to
-- a page that does not exist. Search joins to `occupation_publications` at query time so the
-- gate is always live.

BEGIN;

-- ---------------------------------------------------------------------------------------
-- Curated consumer vocabulary.
--
-- Only terms O*NET does not carry: modern job titles ("ml engineer", "devops engineer"),
-- abbreviations ("swe", "soc analyst"), and everyday words whose canonical title differs
-- ("data entry operator" -> Data Entry Keyers). Everything O*NET already knows is read from
-- onet_alternate_titles instead of being retyped here.
--
-- A row maps a consumer term to a canonical occupation. It never carries a score, and it can
-- never become an occupation: there is no title, no slug and no publication column here, and
-- nothing reads this table as an occupation source.
-- ---------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consumer_aliases (
    id              BIGSERIAL PRIMARY KEY,
    consumer_term   TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    onet_soc_code   TEXT NOT NULL,
    mapping_type    TEXT NOT NULL,
    confidence      NUMERIC(4, 3) NOT NULL,
    source          TEXT NOT NULL DEFAULT 'curated',
    notes           TEXT,
    policy_version  TEXT NOT NULL DEFAULT 'consumer-vocabulary-v1',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT consumer_aliases_mapping_type_check CHECK (mapping_type IN (
        'EXACT_ALIAS', 'COMMON_TITLE', 'ABBREVIATION', 'INDUSTRY_TERM', 'AMBIGUOUS_PARENT')),
    CONSTRAINT consumer_aliases_confidence_check CHECK (confidence > 0 AND confidence <= 1),
    CONSTRAINT consumer_aliases_term_not_blank CHECK (btrim(normalized_term) <> ''),
    -- One term may map to several occupations (that is how breadth is expressed), but the
    -- same term must not map to the same occupation twice.
    CONSTRAINT consumer_aliases_unique_pair UNIQUE (normalized_term, onet_soc_code)
);

COMMENT ON TABLE consumer_aliases IS
  'Consumer vocabulary that O*NET does not carry. Maps an everyday term to a canonical '
  'occupation. Stores no score and never defines an occupation.';
COMMENT ON COLUMN consumer_aliases.mapping_type IS
  'AMBIGUOUS_PARENT means the term is broad and should disambiguate across several '
  'occupations rather than resolve to one.';

CREATE INDEX IF NOT EXISTS consumer_aliases_normalized_idx
    ON consumer_aliases (normalized_term);

-- ---------------------------------------------------------------------------------------
-- The searchable term corpus.
--
-- Covers ALL 1,016 imported occupations, not only the public 507, because a staged
-- occupation still has to be *recognisable*: "data scientist" must be understood well enough
-- to answer "we do not publish that yet" rather than silently returning something unrelated.
-- Publication is enforced by the reader, not by omitting the term.
--
-- `priority` is the ranking floor for the term class. Exact curated aliases outrank exact
-- O*NET titles, which outrank canonical titles matched loosely, and lexical similarity can
-- never overtake any of them — that ordering is what stops "pen tester" reaching
-- Non-Destructive Testing Specialists.
-- ---------------------------------------------------------------------------------------
-- DISTINCT because O*NET repeats a short title across several alternate-title rows for the
-- same occupation (e.g. "CNC Lathe Operator" appears on multiple rows of 51-4012.00). Those
-- are the same searchable term, not several, and the unique index below depends on it.
CREATE MATERIALIZED VIEW IF NOT EXISTS occupation_search_terms AS
SELECT DISTINCT identity_id, onet_soc_code, term, normalized_term, term_type, priority, source
FROM (
    -- Canonical O*NET title.
    SELECT identity.id                                   AS identity_id,
           occupation.onet_soc_code                      AS onet_soc_code,
           occupation.title                              AS term,
           lower(regexp_replace(occupation.title, '[^a-zA-Z0-9]+', ' ', 'g'))
                                                         AS normalized_term,
           'canonical'::TEXT                             AS term_type,
           950                                           AS priority,
           'onet_occupations'::TEXT                      AS source
    FROM onet_occupations occupation
    JOIN canonical_occupation_identities identity
      ON identity.current_source_code = occupation.onet_soc_code
    WHERE occupation.is_current

    UNION ALL

    -- O*NET alternate titles: the 57,543 rows V1 could only see as blob text.
    SELECT identity.id,
           alternate.occupation_code,
           alternate.job_title,
           lower(regexp_replace(alternate.job_title, '[^a-zA-Z0-9]+', ' ', 'g')),
           'alternate'::TEXT,
           900,
           'onet_alternate_titles'::TEXT
    FROM onet_alternate_titles alternate
    JOIN canonical_occupation_identities identity
      ON identity.current_source_code = alternate.occupation_code
    WHERE alternate.is_current

    UNION ALL

    -- O*NET short titles, which are where most genuine abbreviations live.
    SELECT identity.id,
           alternate.occupation_code,
           alternate.short_title,
           lower(regexp_replace(alternate.short_title, '[^a-zA-Z0-9]+', ' ', 'g')),
           'abbreviation'::TEXT,
           900,
           'onet_alternate_titles'::TEXT
    FROM onet_alternate_titles alternate
    JOIN canonical_occupation_identities identity
      ON identity.current_source_code = alternate.occupation_code
    WHERE alternate.is_current
      AND alternate.short_title IS NOT NULL
      AND btrim(alternate.short_title) <> ''

    UNION ALL

    -- Curated consumer vocabulary.
    SELECT identity.id,
           alias.onet_soc_code,
           alias.consumer_term,
           alias.normalized_term,
           CASE WHEN alias.mapping_type = 'AMBIGUOUS_PARENT'
                THEN 'consumer_parent' ELSE 'consumer_alias' END,
           -- Confidence is folded into the floor so that within one tier a 0.85 mapping
           -- outranks a 0.60 one. Without it "martial arts instructor" ranked Coaches and
           -- Scouts (0.60) level with Exercise Trainers (0.85) and broke the tie on title
           -- length, which is meaningless.
           CASE WHEN alias.mapping_type = 'AMBIGUOUS_PARENT'
                THEN 920 ELSE 1000 END + round(alias.confidence * 40)::INT,
           'consumer_aliases'::TEXT
    FROM consumer_aliases alias
    JOIN canonical_occupation_identities identity
      ON identity.current_source_code = alias.onet_soc_code
) AS all_terms
WHERE btrim(normalized_term) <> '';

COMMENT ON MATERIALIZED VIEW occupation_search_terms IS
  'One row per searchable term. Covers all imported occupations so non-public ones stay '
  'recognisable; publication is enforced by the reader at query time, never by omission.';

-- Exact and prefix tiers resolve here. Measured on the benchmark, 80% of consumer queries
-- never reach the trigram index at all.
CREATE INDEX IF NOT EXISTS occupation_search_terms_normalized_idx
    ON occupation_search_terms (normalized_term text_pattern_ops);
CREATE INDEX IF NOT EXISTS occupation_search_terms_identity_idx
    ON occupation_search_terms (identity_id);
-- The fuzzy tail, and the only tier that scans.
CREATE INDEX IF NOT EXISTS occupation_search_terms_trgm_idx
    ON occupation_search_terms USING gin (normalized_term gin_trgm_ops);
-- REFRESH MATERIALIZED VIEW CONCURRENTLY needs a unique index; without it a refresh takes an
-- exclusive lock and search stalls behind an O*NET import.
CREATE UNIQUE INDEX IF NOT EXISTS occupation_search_terms_unique_idx
    ON occupation_search_terms (identity_id, term_type, normalized_term, term);

-- Curated consumer vocabulary, v1. Only terms O*NET does not already carry.
-- Every onet_soc_code below was verified present in onet_occupations at authoring time.
INSERT INTO consumer_aliases
    (consumer_term, normalized_term, onet_soc_code, mapping_type, confidence, source, notes)
VALUES
    ('ai engineer', 'ai engineer', '15-2051.00', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('ai engineer', 'ai engineer', '15-1252.00', 'INDUSTRY_TERM', 0.72, 'curated', 'industry jargon with a defensible canonical home'),
    ('ai engineer', 'ai engineer', '15-1221.00', 'INDUSTRY_TERM', 0.68, 'curated', 'industry jargon with a defensible canonical home'),
    ('back end developer', 'back end developer', '15-1252.00', 'INDUSTRY_TERM', 0.9, 'curated', 'industry jargon with a defensible canonical home'),
    ('backend developer', 'backend developer', '15-1252.00', 'INDUSTRY_TERM', 0.9, 'curated', 'industry jargon with a defensible canonical home'),
    ('beautician', 'beautician', '39-5094.00', 'COMMON_TITLE', 0.8, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('beautician', 'beautician', '39-5012.00', 'COMMON_TITLE', 0.72, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('builder', 'builder', '47-2061.00', 'COMMON_TITLE', 0.7, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('builder', 'builder', '47-2031.00', 'COMMON_TITLE', 0.68, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('builder', 'builder', '11-9021.00', 'COMMON_TITLE', 0.6, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('business analyst', 'business analyst', '13-1111.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('call center agent', 'call center agent', '43-4051.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('car mechanic', 'car mechanic', '49-3023.00', 'COMMON_TITLE', 0.95, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('childminder', 'childminder', '39-9011.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('cleaner', 'cleaner', '37-2011.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('cleaner', 'cleaner', '37-2012.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('clerk', 'clerk', '43-9061.00', 'AMBIGUOUS_PARENT', 0.7, 'curated', 'broad term; disambiguates across several occupations'),
    ('clerk', 'clerk', '43-4051.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('cloud engineer', 'cloud engineer', '15-1244.00', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('cloud engineer', 'cloud engineer', '15-1252.00', 'INDUSTRY_TERM', 0.65, 'curated', 'industry jargon with a defensible canonical home'),
    ('coder', 'coder', '15-1251.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('coder', 'coder', '15-1252.00', 'COMMON_TITLE', 0.8, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('customer support', 'customer support', '43-4051.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('cybersecurity analyst', 'cybersecurity analyst', '15-1212.00', 'COMMON_TITLE', 0.95, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('data analyst', 'data analyst', '15-2051.00', 'COMMON_TITLE', 0.8, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('data analyst', 'data analyst', '15-2041.00', 'COMMON_TITLE', 0.72, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('data analyst', 'data analyst', '13-1111.00', 'COMMON_TITLE', 0.65, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('data entry clerk', 'data entry clerk', '43-9021.00', 'COMMON_TITLE', 0.95, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('data entry operator', 'data entry operator', '43-9021.00', 'COMMON_TITLE', 0.95, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('delivery driver', 'delivery driver', '53-3033.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('delivery driver', 'delivery driver', '53-3031.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('devops engineer', 'devops engineer', '15-1244.00', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('devops engineer', 'devops engineer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('digital marketer', 'digital marketer', '11-2021.00', 'COMMON_TITLE', 0.72, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('digital marketer', 'digital marketer', '13-1161.01', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('doctor', 'doctor', '29-1215.00', 'AMBIGUOUS_PARENT', 0.85, 'curated', 'broad term; disambiguates across several occupations'),
    ('doctor', 'doctor', '29-1216.00', 'AMBIGUOUS_PARENT', 0.82, 'curated', 'broad term; disambiguates across several occupations'),
    ('doctor', 'doctor', '29-1229.00', 'AMBIGUOUS_PARENT', 0.75, 'curated', 'broad term; disambiguates across several occupations'),
    ('driver', 'driver', '53-3032.00', 'AMBIGUOUS_PARENT', 0.8, 'curated', 'broad term; disambiguates across several occupations'),
    ('driver', 'driver', '53-3033.00', 'AMBIGUOUS_PARENT', 0.78, 'curated', 'broad term; disambiguates across several occupations'),
    ('driver', 'driver', '53-3052.00', 'AMBIGUOUS_PARENT', 0.7, 'curated', 'broad term; disambiguates across several occupations'),
    ('driving instructor', 'driving instructor', '25-3021.00', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('engineer', 'engineer', '17-2141.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('engineer', 'engineer', '17-2051.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('engineer', 'engineer', '17-2071.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('estate agent', 'estate agent', '41-9022.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('ethical hacker', 'ethical hacker', '15-1212.00', 'INDUSTRY_TERM', 0.92, 'curated', 'industry jargon with a defensible canonical home'),
    ('factory worker', 'factory worker', '51-9199.00', 'AMBIGUOUS_PARENT', 0.65, 'curated', 'broad term; disambiguates across several occupations'),
    ('factory worker', 'factory worker', '51-2099.00', 'AMBIGUOUS_PARENT', 0.62, 'curated', 'broad term; disambiguates across several occupations'),
    ('farm worker', 'farm worker', '45-2092.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('fisherman', 'fisherman', '45-3031.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('front end developer', 'front end developer', '15-1254.00', 'INDUSTRY_TERM', 0.85, 'curated', 'industry jargon with a defensible canonical home'),
    ('front end developer', 'front end developer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('frontend developer', 'frontend developer', '15-1254.00', 'INDUSTRY_TERM', 0.85, 'curated', 'industry jargon with a defensible canonical home'),
    ('frontend developer', 'frontend developer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('full stack developer', 'full stack developer', '15-1252.00', 'INDUSTRY_TERM', 0.88, 'curated', 'industry jargon with a defensible canonical home'),
    ('full stack developer', 'full stack developer', '15-1254.00', 'INDUSTRY_TERM', 0.75, 'curated', 'industry jargon with a defensible canonical home'),
    ('game developer', 'game developer', '15-1255.01', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('game developer', 'game developer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('gardener', 'gardener', '37-3011.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('headteacher', 'headteacher', '11-9032.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('help desk', 'help desk', '15-1232.00', 'INDUSTRY_TERM', 0.9, 'curated', 'industry jargon with a defensible canonical home'),
    ('hotel receptionist', 'hotel receptionist', '43-4081.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('it support', 'it support', '15-1232.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('lab technician', 'lab technician', '29-2012.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('lab technician', 'lab technician', '29-2011.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('lecturer', 'lecturer', '25-1022.00', 'AMBIGUOUS_PARENT', 0.63, 'curated', 'broad term; disambiguates across several occupations'),
    ('lecturer', 'lecturer', '25-1042.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('lecturer', 'lecturer', '25-1031.00', 'AMBIGUOUS_PARENT', 0.58, 'curated', 'broad term; disambiguates across several occupations'),
    ('machine learning engineer', 'machine learning engineer', '15-2051.00', 'INDUSTRY_TERM', 0.85, 'curated', 'industry jargon with a defensible canonical home'),
    ('machine learning engineer', 'machine learning engineer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('machine learning engineer', 'machine learning engineer', '15-1221.00', 'INDUSTRY_TERM', 0.65, 'curated', 'industry jargon with a defensible canonical home'),
    ('martial arts instructor', 'martial arts instructor', '39-9031.00', 'INDUSTRY_TERM', 0.85, 'curated', 'industry jargon with a defensible canonical home'),
    ('martial arts instructor', 'martial arts instructor', '27-2022.00', 'INDUSTRY_TERM', 0.6, 'curated', 'industry jargon with a defensible canonical home'),
    ('maths teacher', 'maths teacher', '25-2031.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('maths teacher', 'maths teacher', '25-1022.00', 'COMMON_TITLE', 0.65, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('mechanic', 'mechanic', '49-3023.00', 'AMBIGUOUS_PARENT', 0.85, 'curated', 'broad term; disambiguates across several occupations'),
    ('mechanic', 'mechanic', '49-3042.00', 'AMBIGUOUS_PARENT', 0.7, 'curated', 'broad term; disambiguates across several occupations'),
    ('ml engineer', 'ml engineer', '15-2051.00', 'ABBREVIATION', 0.85, 'curated', 'initialism in common use'),
    ('ml engineer', 'ml engineer', '15-1252.00', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('ml engineer', 'ml engineer', '15-1221.00', 'INDUSTRY_TERM', 0.65, 'curated', 'industry jargon with a defensible canonical home'),
    ('mobile app developer', 'mobile app developer', '15-1252.00', 'INDUSTRY_TERM', 0.88, 'curated', 'industry jargon with a defensible canonical home'),
    ('network engineer', 'network engineer', '15-1231.00', 'INDUSTRY_TERM', 0.8, 'curated', 'industry jargon with a defensible canonical home'),
    ('network engineer', 'network engineer', '15-1244.00', 'INDUSTRY_TERM', 0.75, 'curated', 'industry jargon with a defensible canonical home'),
    ('nurse', 'nurse', '29-1141.00', 'AMBIGUOUS_PARENT', 0.92, 'curated', 'broad term; disambiguates across several occupations'),
    ('nurse', 'nurse', '29-2061.00', 'AMBIGUOUS_PARENT', 0.72, 'curated', 'broad term; disambiguates across several occupations'),
    ('office manager', 'office manager', '43-1011.00', 'COMMON_TITLE', 0.8, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('office manager', 'office manager', '11-3012.00', 'COMMON_TITLE', 0.7, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('operations manager', 'operations manager', '11-1021.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('pen tester', 'pen tester', '15-1212.00', 'INDUSTRY_TERM', 0.92, 'curated', 'industry jargon with a defensible canonical home'),
    ('penetration tester', 'penetration tester', '15-1212.00', 'INDUSTRY_TERM', 0.95, 'curated', 'industry jargon with a defensible canonical home'),
    ('principal', 'principal', '11-9032.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('prison officer', 'prison officer', '33-3012.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('product designer', 'product designer', '27-1021.00', 'INDUSTRY_TERM', 0.72, 'curated', 'industry jargon with a defensible canonical home'),
    ('product designer', 'product designer', '15-1255.00', 'INDUSTRY_TERM', 0.68, 'curated', 'industry jargon with a defensible canonical home'),
    ('product manager', 'product manager', '13-1082.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('product manager', 'product manager', '11-1021.00', 'COMMON_TITLE', 0.6, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('professor', 'professor', '25-1022.00', 'AMBIGUOUS_PARENT', 0.65, 'curated', 'broad term; disambiguates across several occupations'),
    ('professor', 'professor', '25-1042.00', 'AMBIGUOUS_PARENT', 0.62, 'curated', 'broad term; disambiguates across several occupations'),
    ('professor', 'professor', '25-1031.00', 'AMBIGUOUS_PARENT', 0.6, 'curated', 'broad term; disambiguates across several occupations'),
    ('programmer', 'programmer', '15-1251.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('programmer', 'programmer', '15-1252.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('qa engineer', 'qa engineer', '15-1253.00', 'COMMON_TITLE', 0.9, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('qa engineer', 'qa engineer', '15-1252.00', 'INDUSTRY_TERM', 0.65, 'curated', 'industry jargon with a defensible canonical home'),
    ('salesman', 'salesman', '41-2031.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('salesman', 'salesman', '41-4012.00', 'COMMON_TITLE', 0.7, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('school teacher', 'school teacher', '25-2021.00', 'AMBIGUOUS_PARENT', 0.88, 'curated', 'broad term; disambiguates across several occupations'),
    ('school teacher', 'school teacher', '25-2031.00', 'AMBIGUOUS_PARENT', 0.88, 'curated', 'broad term; disambiguates across several occupations'),
    ('security analyst', 'security analyst', '15-1212.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('seo specialist', 'seo specialist', '13-1161.01', 'INDUSTRY_TERM', 0.95, 'curated', 'industry jargon with a defensible canonical home'),
    ('shop assistant', 'shop assistant', '41-2031.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('shopkeeper', 'shopkeeper', '41-1011.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('shopkeeper', 'shopkeeper', '41-2031.00', 'COMMON_TITLE', 0.7, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('soc analyst', 'soc analyst', '15-1212.00', 'ABBREVIATION', 0.88, 'curated', 'initialism in common use'),
    ('social media manager', 'social media manager', '13-1161.01', 'INDUSTRY_TERM', 0.7, 'curated', 'industry jargon with a defensible canonical home'),
    ('social media manager', 'social media manager', '27-3031.00', 'INDUSTRY_TERM', 0.65, 'curated', 'industry jargon with a defensible canonical home'),
    ('software engineer', 'software engineer', '15-1252.00', 'COMMON_TITLE', 0.98, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('soldier', 'soldier', '55-3016.00', 'COMMON_TITLE', 0.75, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('solicitor', 'solicitor', '23-1011.00', 'COMMON_TITLE', 0.92, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('swe', 'swe', '15-1252.00', 'ABBREVIATION', 0.95, 'curated', 'initialism in common use'),
    ('sysadmin', 'sysadmin', '15-1244.00', 'ABBREVIATION', 0.95, 'curated', 'initialism in common use'),
    ('system administrator', 'system administrator', '15-1244.00', 'COMMON_TITLE', 0.95, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('teacher', 'teacher', '25-2021.00', 'AMBIGUOUS_PARENT', 0.85, 'curated', 'broad term; disambiguates across several occupations'),
    ('teacher', 'teacher', '25-2031.00', 'AMBIGUOUS_PARENT', 0.85, 'curated', 'broad term; disambiguates across several occupations'),
    ('teacher', 'teacher', '25-2012.00', 'AMBIGUOUS_PARENT', 0.8, 'curated', 'broad term; disambiguates across several occupations'),
    ('teacher', 'teacher', '25-2051.00', 'AMBIGUOUS_PARENT', 0.75, 'curated', 'broad term; disambiguates across several occupations'),
    ('teacher', 'teacher', '25-1022.00', 'AMBIGUOUS_PARENT', 0.65, 'curated', 'broad term; disambiguates across several occupations'),
    ('therapist', 'therapist', '29-1123.00', 'AMBIGUOUS_PARENT', 0.7, 'curated', 'broad term; disambiguates across several occupations'),
    ('therapist', 'therapist', '21-1013.00', 'AMBIGUOUS_PARENT', 0.65, 'curated', 'broad term; disambiguates across several occupations'),
    ('therapist', 'therapist', '29-1229.00', 'AMBIGUOUS_PARENT', 0.55, 'curated', 'broad term; disambiguates across several occupations'),
    ('train driver', 'train driver', '53-4011.00', 'COMMON_TITLE', 0.88, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('ui designer', 'ui designer', '15-1255.00', 'INDUSTRY_TERM', 0.88, 'curated', 'industry jargon with a defensible canonical home'),
    ('ux designer', 'ux designer', '15-1255.00', 'INDUSTRY_TERM', 0.9, 'curated', 'industry jargon with a defensible canonical home'),
    ('warehouse worker', 'warehouse worker', '53-7062.00', 'COMMON_TITLE', 0.85, 'curated', 'everyday name for an occupation whose canonical title differs'),
    ('warehouse worker', 'warehouse worker', '53-7065.00', 'COMMON_TITLE', 0.72, 'curated', 'everyday name for an occupation whose canonical title differs')
ON CONFLICT (normalized_term, onet_soc_code) DO NOTHING;
-- 135 mappings across 80 consumer terms

-- The view is populated after the seed so curated terms are present from the first refresh.
REFRESH MATERIALIZED VIEW occupation_search_terms;

COMMIT;
