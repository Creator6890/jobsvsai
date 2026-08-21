BEGIN;

CREATE TABLE frontier_ai_capability_index_tracks (
  id BIGSERIAL PRIMARY KEY,
  index_version_id BIGINT NOT NULL REFERENCES frontier_ai_capability_index_versions(id),
  track_code TEXT NOT NULL CHECK (track_code IN ('commercially_deployable','technical_frontier')),
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','provisional','review','approved','retired')),
  expected_capability_count INTEGER NOT NULL CHECK (expected_capability_count > 0),
  assessment_date DATE,
  source_id BIGINT NOT NULL REFERENCES data_sources(id),
  methodology_notes TEXT NOT NULL,
  provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (index_version_id,track_code),
  UNIQUE (id,index_version_id),
  CHECK (status='draft' OR assessment_date IS NOT NULL)
);

INSERT INTO frontier_ai_capability_index_tracks (
  index_version_id,track_code,name,description,status,expected_capability_count,
  assessment_date,source_id,methodology_notes,provenance,created_by
)
SELECT index_version.id,track.track_code,track.name,track.description,track.status,
  index_version.expected_capability_count,track.assessment_date,index_version.source_id,
  track.methodology_notes,track.provenance,'system:migration-017'
FROM frontier_ai_capability_index_versions index_version
CROSS JOIN (VALUES
  ('commercially_deployable','Commercially deployable',
   'Capability available through products or APIs with practical deployment constraints applied.',
   'provisional','2026-08-20'::date,
   'JobsVsAI synthesis of supplied 2026-Q3 values. Benchmarks are evidence signals, not direct conversions to the 0-100 index.',
   '{"assessment_cycle":"2026-Q3","values_supplied_by":"JobsVsAI","provisional":true,"production_scoring":false}'::jsonb),
  ('technical_frontier','Technical frontier',
   'Best demonstrated technical capability, including research previews and specialist systems.',
   'draft',NULL::date,
   'Track is reserved and versioned; no score is assigned until an approved technical-frontier value set is supplied.',
   '{"assessment_cycle":"2026-Q3","values_assigned":false,"do_not_infer":true,"production_scoring":false}'::jsonb)
) AS track(track_code,name,description,status,assessment_date,methodology_notes,provenance)
WHERE index_version.index_version='frontier-ai-index-v1';

ALTER TABLE frontier_ai_capability_index_entries
  ADD COLUMN track_id BIGINT,
  ADD COLUMN assessment_status TEXT NOT NULL DEFAULT 'provisional'
    CHECK (assessment_status IN ('provisional','reviewed','approved','superseded')),
  ADD COLUMN assessment_date DATE;

DO $$
DECLARE constraint_record RECORD;
BEGIN
  FOR constraint_record IN
    SELECT conname FROM pg_constraint
    WHERE conrelid='frontier_ai_capability_index_entries'::regclass
      AND contype='u'
      AND pg_get_constraintdef(oid)='UNIQUE (index_version_id, capability_definition_id)'
  LOOP
    EXECUTE format('ALTER TABLE frontier_ai_capability_index_entries DROP CONSTRAINT %I',constraint_record.conname);
  END LOOP;
END $$;

ALTER TABLE frontier_ai_capability_index_entries
  ALTER COLUMN track_id SET NOT NULL,
  ALTER COLUMN assessment_date SET NOT NULL,
  ADD CONSTRAINT frontier_index_entry_track_fk
    FOREIGN KEY (track_id,index_version_id)
    REFERENCES frontier_ai_capability_index_tracks(id,index_version_id),
  ADD CONSTRAINT frontier_index_entry_track_capability_key
    UNIQUE (index_version_id,track_id,capability_definition_id);

ALTER TABLE frontier_ai_capability_evidence_records
  ADD COLUMN track_id BIGINT,
  ADD COLUMN source_tier TEXT
    CHECK (source_tier IN ('tier_1_provider_primary','tier_1_research_primary','tier_2_independent_benchmark','tier_3_contextual')),
  ADD COLUMN benchmark_name TEXT,
  ADD COLUMN reported_result TEXT,
  ADD COLUMN source_reference TEXT;

ALTER TABLE frontier_ai_capability_evidence_records
  ALTER COLUMN track_id SET NOT NULL,
  ALTER COLUMN source_tier SET NOT NULL,
  ALTER COLUMN benchmark_name SET NOT NULL,
  ALTER COLUMN reported_result SET NOT NULL,
  ALTER COLUMN source_reference SET NOT NULL,
  ADD CONSTRAINT frontier_index_evidence_track_fk
    FOREIGN KEY (track_id,index_version_id)
    REFERENCES frontier_ai_capability_index_tracks(id,index_version_id),
  ADD CONSTRAINT frontier_index_evidence_record_key
    UNIQUE (track_id,capability_definition_id,benchmark_name,source_reference);

INSERT INTO data_sources (name,source_url,version,published_at,metadata) VALUES
  ('OpenAI GPT-5.5 release and evaluations','https://openai.com/index/introducing-gpt-5-5/','2026-04-23','2026-04-23T00:00:00Z','{"publisher":"OpenAI","source_tier":"tier_1_provider_primary"}'),
  ('OpenAI GPT-5.6 release and evaluations','https://openai.com/index/gpt-5-6/','2026-07-09','2026-07-09T00:00:00Z','{"publisher":"OpenAI","source_tier":"tier_1_provider_primary"}'),
  ('Google DeepMind Gemini 3.5 Flash model card','https://deepmind.google/models/model-cards/gemini-3-5-flash/','2026-05-19','2026-05-19T00:00:00Z','{"publisher":"Google DeepMind","source_tier":"tier_1_provider_primary"}'),
  ('Google DeepMind Gemini 3.1 Flash Image model card','https://deepmind.google/models/model-cards/gemini-3-1-flash-image/','2026-02-26','2026-02-26T00:00:00Z','{"publisher":"Google DeepMind","source_tier":"tier_1_provider_primary"}'),
  ('PieArena negotiation benchmark paper','https://arxiv.org/abs/2602.05302','2026-02-05','2026-02-05T00:00:00Z','{"publisher":"arXiv","source_tier":"tier_1_research_primary","authors":"Zhu et al."}'),
  ('Google DeepMind Gemini Robotics-ER 1.6','https://deepmind.google/blog/gemini-robotics-er-1-6/','2026-04-14','2026-04-14T00:00:00Z','{"publisher":"Google DeepMind","source_tier":"tier_1_provider_primary"}'),
  ('Google DeepMind Gemini Robotics On-Device 2 model card','https://deepmind.google/models/model-cards/gemini-robotics-on-device-2/','2026-07-30','2026-07-30T00:00:00Z','{"publisher":"Google DeepMind","source_tier":"tier_1_provider_primary"}'),
  ('Google DeepMind Gemini Robotics ER 2 results','https://deepmind.google/models/gemini-robotics/embodied-reasoning/','2026-07-30','2026-07-30T00:00:00Z','{"publisher":"Google DeepMind","source_tier":"tier_1_provider_primary"}')
ON CONFLICT (name) DO NOTHING;

WITH assessment(slug,score,confidence,rationale,evidence_key) AS (VALUES
  ('language-comprehension',96,92,'Commercial systems show near-saturated short-form instruction following and very strong long-context reading, while residual ambiguity and extreme-context failures prevent a perfect score.','gpt55-mrcr'),
  ('language-generation',97,92,'Commercial systems reliably produce high-quality professional prose and structured deliverables across broad domains; factuality and nuanced style control remain residual limitations.','gpt55-gdpval'),
  ('information-retrieval',95,90,'Deployed browsing agents demonstrate very high performance on adversarial multi-hop retrieval, with remaining failures on source quality, access and long-tail synthesis.','gpt56-browsecomp'),
  ('quantitative-reasoning',91,86,'Frontier commercial models are highly capable on routine and advanced quantitative work but remain materially below saturation on the hardest novel mathematics.','gpt55-frontiermath'),
  ('general-reasoning',90,88,'Broad expert reasoning is strong across science and professional tasks, but difficult novel problems still expose substantial headroom.','gpt55-reasoning'),
  ('software-code-generation',96,92,'Commercial coding agents resolve a large share of real repository and terminal tasks and are broadly deployable, though difficult end-to-end failures remain.','gpt55-coding'),
  ('visual-understanding',93,90,'Commercial multimodal systems perform strongly on expert visual reasoning and improve further with tools, while spatial and fine-detail errors persist.','gpt56-multimodal'),
  ('visual-content-generation',96,90,'Commercial image systems achieve leading human-preference and editing results across diverse generation tasks, with known text, consistency and factuality limitations.','gemini-image'),
  ('planning-workflow-execution',87,84,'Commercial agents complete increasingly long multi-step workflows, but reliability compounds across steps and still requires monitoring for consequential work.','gemini-mcp'),
  ('tool-computer-operation',86,85,'Commercial agents can operate real software and operating systems at high but not human-level reliability; deployment remains sensitive to interface changes and safeguards.','gpt55-osworld'),
  ('interpersonal-social-interaction',62,72,'Models handle scripted service interactions well but realistic negotiation evidence reveals uneven reputation, deception and trust behavior, limiting unsupervised deployment.','piearena-social'),
  ('persuasion-negotiation',60,74,'Frontier agents can match trained negotiators on deal outcomes, yet robustness, truthfulness and reputation trade-offs make commercially safe persuasion materially less capable than raw performance suggests.','piearena-negotiation'),
  ('physical-perception',38,68,'Specialist embodied models show strong instrument reading and success detection, but capability is narrow, sensor-dependent and not a general commercially deployable perception stack.','robotics-perception'),
  ('fine-physical-manipulation',10,62,'Robotic manipulation has meaningful specialist successes, but availability is restricted and performance depends on embodiment-specific post-training and demonstrations.','robotics-manipulation'),
  ('mobility-real-world-operation',12,60,'Physical-agent systems can coordinate planning and limited real-world execution, but general mobility, safety and high-degree-of-freedom control remain preview-stage constraints.','robotics-mobility')
), context AS (
  SELECT index_version.id index_version_id,index_version.source_id,track.id track_id,taxonomy.id taxonomy_version_id
  FROM frontier_ai_capability_index_versions index_version
  JOIN frontier_ai_capability_index_tracks track ON track.index_version_id=index_version.id AND track.track_code='commercially_deployable'
  JOIN ai_capability_taxonomy_versions taxonomy ON taxonomy.id=index_version.taxonomy_version_id
  WHERE index_version.index_version='frontier-ai-index-v1'
)
INSERT INTO frontier_ai_capability_index_entries (
  index_version_id,track_id,capability_definition_id,capability_score,confidence,source_type,
  provider_name,observed_at,assessment_status,assessment_date,rationale,benchmark_evidence,
  provenance,source_id,created_by
)
SELECT context.index_version_id,context.track_id,definition.id,assessment.score,assessment.confidence,
  'expert_synthesis','JobsVsAI','2026-08-20','provisional','2026-08-20',assessment.rationale,
  jsonb_build_array(jsonb_build_object(
    'evidenceKey',assessment.evidence_key,
    'interpretation','Evidence signal only; benchmark result is not numerically converted into the JobsVsAI score.',
    'assessmentCycle','2026-Q3'
  )),
  jsonb_build_object('assessment_cycle','2026-Q3','track','commercially_deployable','provisional',true,
    'supplied_score',true,'occupation_score_input',false),
  context.source_id,'system:migration-017'
FROM assessment
JOIN context ON true
JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=context.taxonomy_version_id AND definition.slug=assessment.slug;

WITH evidence(
  slug,source_name,source_type,provider_name,model_name,model_version,evidence_date,
  benchmark_name,reported_result,rationale,confidence,evidence_payload
) AS (VALUES
  ('language-comprehension','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'MRCR v2 8-needle','98.1% at 4K-8K; 93.0% at 8K-16K; 83.1% at 64K-128K','Supports very strong deployed reading and retrieval across long contexts while documenting degradation at extreme lengths.',92,'{"metric":"accuracy","scope":"long-context language comprehension"}'::jsonb),
  ('language-generation','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'GDPval wins or ties','84.9%','Provides a broad professional-deliverable signal for commercially available language generation; not treated as a direct score conversion.',88,'{"metric":"human preference wins_or_ties","scope":"professional knowledge-work deliverables"}'::jsonb),
  ('information-retrieval','OpenAI GPT-5.6 release and evaluations','provider_benchmark','OpenAI','GPT-5.6 Sol Ultra','2026-07-09','2026-07-09'::date,'BrowseComp','92.2%','Direct evidence for commercially available agentic browsing, retrieval and multi-source synthesis.',92,'{"metric":"accuracy","harness":"agentic browsing"}'::jsonb),
  ('quantitative-reasoning','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'FrontierMath','51.7% on Tiers 1-3; 35.4% on Tier 4','Shows substantial capability on extremely difficult mathematics while preserving evidence of unresolved frontier headroom.',86,'{"metric":"accuracy","scope":"frontier mathematics"}'::jsonb),
  ('general-reasoning','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'GPQA Diamond and Humanity''s Last Exam','93.6% GPQA Diamond; 52.2% HLE with tools','Combines a strong expert-science signal with a difficult broad-reasoning benchmark that remains far from saturation.',88,'{"metrics":["GPQA Diamond","Humanity''s Last Exam with tools"]}'::jsonb),
  ('software-code-generation','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'Terminal-Bench 2.0 and SWE-Bench Pro Public','82.7% Terminal-Bench; 58.6% SWE-Bench Pro','Supports high commercial coding capability across terminal and repository tasks while retaining difficult failure cases.',91,'{"metrics":["Terminal-Bench 2.0","SWE-Bench Pro Public"]}'::jsonb),
  ('visual-understanding','OpenAI GPT-5.6 release and evaluations','provider_benchmark','OpenAI','GPT-5.6 Sol','2026-07-09','2026-07-09'::date,'MMMU Pro','83.0% without tools; 84.6% with tools','Evidence for strong commercially available multimodal interpretation across expert visual domains.',90,'{"metric":"accuracy","scope":"multimodal expert reasoning"}'::jsonb),
  ('visual-content-generation','Google DeepMind Gemini 3.1 Flash Image model card','provider_benchmark','Google DeepMind','Gemini 3.1 Flash Image','2026-02-26','2026-02-26'::date,'GenAI-Bench visual quality','1140 ± 6 Elo with thinking, text search and image search','Human-preference evidence across commercial text-to-image generation; limitations are retained in the assessment rationale.',90,'{"metric":"Elo","evaluation":"side-by-side human preference"}'::jsonb),
  ('planning-workflow-execution','Google DeepMind Gemini 3.5 Flash model card','provider_benchmark','Google DeepMind','Gemini 3.5 Flash','2026-05-19','2026-05-19'::date,'MCP Atlas','83.6%','Direct signal for multi-step MCP workflows, tempered because benchmark execution does not remove production reliability constraints.',86,'{"metric":"success_rate","scope":"multi-step agentic workflows"}'::jsonb),
  ('tool-computer-operation','OpenAI GPT-5.5 release and evaluations','provider_benchmark','OpenAI','GPT-5.5','2026-04-23','2026-04-23'::date,'OSWorld-Verified','78.7%','Direct evidence for commercially available full-computer operation; the residual failure rate remains operationally material.',88,'{"metric":"success_rate","scope":"full operating-system control"}'::jsonb),
  ('interpersonal-social-interaction','PieArena negotiation benchmark paper','research_paper','Zhu et al.','GPT-5 / GPT-5.2','arXiv:2602.05302','2026-02-05'::date,'PieArena behavioral profile','GPT-5/5.2 reputation about 0.64-0.65; GPT-5.2 lie rate about 33.9%','Realistic interaction evidence shows capable social behavior alongside material trust and reputation limitations.',76,'{"metric":"behavioral_profile","sample":"over 25,000 agent negotiation transcripts"}'::jsonb),
  ('persuasion-negotiation','PieArena negotiation benchmark paper','research_paper','Zhu et al.','GPT-5','arXiv:2602.05302','2026-02-05'::date,'PieArena human comparison','GPT-5 matched or outperformed trained MBA students; human-vs-agent pie-share difference was not significant (p=0.2674)','Supports strong raw negotiation performance but explicitly preserves documented robustness, truthfulness and trustworthiness caveats.',78,'{"metric":"negotiation_outcomes","human_sessions":167,"agent_transcripts":"over 25,000"}'::jsonb),
  ('physical-perception','Google DeepMind Gemini Robotics-ER 1.6','provider_benchmark','Google DeepMind','Gemini Robotics-ER 1.6','2026-04-14','2026-04-14'::date,'Instrument reading','93% success with agentic vision; 86% without agentic vision','Demonstrates strong specialist physical perception through an API, but only on a narrow embodied-reasoning task.',74,'{"metric":"success_rate","scope":"instrument reading"}'::jsonb),
  ('fine-physical-manipulation','Google DeepMind Gemini Robotics On-Device 2 model card','provider_benchmark','Google DeepMind','Gemini Robotics On-Device 2','2026-07-30','2026-07-30'::date,'Novel-platform data scaling','53.3% SO101 and 75.6% Dexmate final success after post-training','Shows real manipulation progress while documenting trusted-tester availability, platform adaptation and limited out-of-distribution generalization.',70,'{"metric":"success_rate","availability":"trusted testers"}'::jsonb),
  ('mobility-real-world-operation','Google DeepMind Gemini Robotics ER 2 results','provider_benchmark','Google DeepMind','Gemini Robotics ER 2','2026-07-30','2026-07-30'::date,'Physical agent performance','60.0% controlling real VLA; 42.9% controlling simulated VLA','Evidence of real-world physical-agent coordination, tempered because the reasoning model delegates motor execution and remains preview-stage.',68,'{"metric":"success_rate","scope":"physical agent control through VLA"}'::jsonb)
), context AS (
  SELECT index_version.id index_version_id,index_version.taxonomy_version_id,track.id track_id
  FROM frontier_ai_capability_index_versions index_version
  JOIN frontier_ai_capability_index_tracks track ON track.index_version_id=index_version.id AND track.track_code='commercially_deployable'
  WHERE index_version.index_version='frontier-ai-index-v1'
)
INSERT INTO frontier_ai_capability_evidence_records (
  index_version_id,track_id,capability_definition_id,source_type,source_tier,provider_name,
  model_name,model_version,evidence_date,title,benchmark_name,reported_result,source_uri,
  source_reference,evidence_payload,rationale,confidence,source_id,provenance,created_by
)
SELECT context.index_version_id,context.track_id,definition.id,evidence.source_type,
  CASE WHEN evidence.source_type='research_paper' THEN 'tier_1_research_primary' ELSE 'tier_1_provider_primary' END,
  evidence.provider_name,evidence.model_name,evidence.model_version,evidence.evidence_date,
  evidence.benchmark_name,evidence.benchmark_name,evidence.reported_result,source.source_url,
  source.source_url,evidence.evidence_payload,evidence.rationale,evidence.confidence,source.id,
  jsonb_build_object('assessment_cycle','2026-Q3','track','commercially_deployable',
    'reported_result_preserved',true,'retrieved_at','2026-08-20','score_conversion','none'),
  'system:migration-017'
FROM evidence
JOIN context ON true
JOIN ai_capability_definitions definition ON definition.taxonomy_version_id=context.taxonomy_version_id AND definition.slug=evidence.slug
JOIN data_sources source ON source.name=evidence.source_name;

CREATE TRIGGER frontier_index_tracks_append_only
  BEFORE UPDATE OR DELETE ON frontier_ai_capability_index_tracks
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_enrichment_history_mutation();

CREATE OR REPLACE FUNCTION validate_frontier_ai_capability_index(index_key BIGINT)
RETURNS BOOLEAN LANGUAGE plpgsql AS $$
DECLARE
  index_row frontier_ai_capability_index_versions%ROWTYPE;
  track_row frontier_ai_capability_index_tracks%ROWTYPE;
  entry_count INTEGER;
  invalid_entries INTEGER;
  entries_without_evidence INTEGER;
BEGIN
  SELECT * INTO index_row FROM frontier_ai_capability_index_versions WHERE id=index_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'Unknown Frontier AI Capability Index version %',index_key; END IF;
  IF NOT EXISTS (SELECT 1 FROM frontier_ai_capability_index_tracks WHERE index_version_id=index_key) THEN
    RAISE EXCEPTION 'Frontier index % has no assessment tracks',index_key;
  END IF;

  FOR track_row IN SELECT * FROM frontier_ai_capability_index_tracks WHERE index_version_id=index_key LOOP
    SELECT count(*),count(*) FILTER (WHERE definition.taxonomy_version_id<>index_row.taxonomy_version_id),
      count(*) FILTER (WHERE NOT EXISTS (
        SELECT 1 FROM frontier_ai_capability_evidence_records evidence
        WHERE evidence.index_version_id=index_key AND evidence.track_id=track_row.id
          AND evidence.capability_definition_id=entry.capability_definition_id
      ))
    INTO entry_count,invalid_entries,entries_without_evidence
    FROM frontier_ai_capability_index_entries entry
    JOIN ai_capability_definitions definition ON definition.id=entry.capability_definition_id
    WHERE entry.index_version_id=index_key AND entry.track_id=track_row.id;

    IF invalid_entries>0 THEN RAISE EXCEPTION 'Frontier index % track % mixes taxonomy versions',index_key,track_row.track_code; END IF;
    IF entry_count NOT IN (0,track_row.expected_capability_count) THEN
      RAISE EXCEPTION 'Frontier index % track % must be empty or complete: expected %, found %',index_key,track_row.track_code,track_row.expected_capability_count,entry_count;
    END IF;
    IF entry_count>0 AND entries_without_evidence>0 THEN
      RAISE EXCEPTION 'Frontier index % track % has % capability values without evidence',index_key,track_row.track_code,entries_without_evidence;
    END IF;
    IF track_row.status IN ('review','approved') AND entry_count<>track_row.expected_capability_count THEN
      RAISE EXCEPTION 'Frontier index % track % is % but incomplete',index_key,track_row.track_code,track_row.status;
    END IF;
  END LOOP;
  RETURN true;
END $$;

DROP VIEW frontier_ai_capability_index_validation;

CREATE VIEW frontier_ai_capability_index_validation AS
SELECT index_version.id index_version_id,index_version.index_version,index_version.status,
  index_version.expected_capability_count,
  count(DISTINCT track.id) assessment_tracks,
  count(DISTINCT track.id) FILTER (WHERE EXISTS (
    SELECT 1 FROM frontier_ai_capability_index_entries populated WHERE populated.track_id=track.id
  )) populated_tracks,
  count(DISTINCT entry.id) capability_values,
  count(DISTINCT entry.id) FILTER (WHERE track.track_code='commercially_deployable') commercially_deployable_values,
  count(DISTINCT entry.id) FILTER (WHERE track.track_code='technical_frontier') technical_frontier_values,
  count(DISTINCT entry.id) FILTER (WHERE entry.assessment_status='provisional') provisional_values,
  count(DISTINCT evidence.id) evidence_records,
  validate_frontier_ai_capability_index(index_version.id) index_valid
FROM frontier_ai_capability_index_versions index_version
LEFT JOIN frontier_ai_capability_index_tracks track ON track.index_version_id=index_version.id
LEFT JOIN frontier_ai_capability_index_entries entry ON entry.index_version_id=index_version.id AND entry.track_id=track.id
LEFT JOIN frontier_ai_capability_evidence_records evidence ON evidence.index_version_id=index_version.id AND evidence.track_id=track.id
GROUP BY index_version.id;

SELECT validate_frontier_ai_capability_index(id)
FROM frontier_ai_capability_index_versions WHERE index_version='frontier-ai-index-v1';

COMMIT;
