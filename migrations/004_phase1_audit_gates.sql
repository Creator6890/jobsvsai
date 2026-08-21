BEGIN;

ALTER TABLE occupations
  ADD COLUMN IF NOT EXISTS education_requirement SMALLINT NOT NULL DEFAULT 2
    CHECK (education_requirement BETWEEN 0 AND 4);

ALTER TABLE occupation_scores
  ADD COLUMN IF NOT EXISTS task_exposure NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS ai_capability_proximity NUMERIC(5,2);

UPDATE scoring_model_versions
SET replacement_config = (replacement_config - 'exposure') ||
  jsonb_build_object('task_exposure', COALESCE(replacement_config->'task_exposure', replacement_config->'exposure'))
WHERE replacement_config ? 'exposure' OR NOT replacement_config ? 'task_exposure';

UPDATE occupations SET education_requirement = CASE slug
  WHEN 'nurse-practitioner' THEN 4
  WHEN 'aircraft-mechanic' THEN 1
  ELSE 2
END;

INSERT INTO skills (name, description, source_id)
SELECT skill.name, skill.description, source.id
FROM (VALUES
  ('Visual communication', 'Communicate ideas through visual systems'),
  ('Client communication', 'Discover needs and communicate with clients'),
  ('Creative problem solving', 'Frame and solve ambiguous creative problems'),
  ('Brand strategy', 'Develop positioning and commercial brand direction'),
  ('Research synthesis', 'Combine evidence into useful findings'),
  ('Interviewing', 'Conduct contextual human interviews'),
  ('Stakeholder facilitation', 'Align people around decisions'),
  ('Software development', 'Design and implement software'),
  ('System architecture', 'Design technical system boundaries'),
  ('Debugging', 'Diagnose and correct technical failures'),
  ('Financial analysis', 'Analyze financial records and decisions'),
  ('Audit judgment', 'Evaluate financial evidence and risk'),
  ('Clinical judgment', 'Make accountable clinical decisions'),
  ('Patient care', 'Deliver contextual direct patient care'),
  ('Mechanical repair', 'Diagnose and repair physical equipment'),
  ('Safety compliance', 'Apply safety and regulatory controls'),
  ('Incident response', 'Coordinate response to security incidents'),
  ('Security analysis', 'Assess adversarial security evidence'),
  ('Relationship management', 'Build trusted long-term relationships'),
  ('Regulatory advice', 'Give advice within regulated constraints')
) AS skill(name, description)
CROSS JOIN data_sources source
WHERE source.name = 'Occupation taxonomy demo'
ON CONFLICT (name) DO NOTHING;

INSERT INTO occupation_skills (occupation_id, skill_id, importance)
SELECT occupation.id, skill.id, mapping.importance
FROM (VALUES
  ('graphic-designer','Visual communication',96),
  ('graphic-designer','Client communication',78),
  ('graphic-designer','Creative problem solving',92),
  ('brand-strategist','Brand strategy',96),
  ('brand-strategist','Client communication',78),
  ('brand-strategist','Creative problem solving',88),
  ('brand-strategist','Stakeholder facilitation',90),
  ('ux-researcher','Research synthesis',94),
  ('ux-researcher','Interviewing',96),
  ('ux-researcher','Client communication',72),
  ('ux-researcher','Stakeholder facilitation',86),
  ('software-developer','Software development',96),
  ('software-developer','System architecture',92),
  ('software-developer','Debugging',90),
  ('software-developer','Stakeholder facilitation',70),
  ('accountant','Financial analysis',94),
  ('accountant','Audit judgment',92),
  ('accountant','Regulatory advice',78),
  ('accountant','Client communication',66),
  ('nurse-practitioner','Clinical judgment',98),
  ('nurse-practitioner','Patient care',98),
  ('nurse-practitioner','Client communication',82),
  ('aircraft-mechanic','Mechanical repair',98),
  ('aircraft-mechanic','Safety compliance',98),
  ('aircraft-mechanic','Debugging',72),
  ('cybersecurity-analyst','Security analysis',96),
  ('cybersecurity-analyst','Incident response',96),
  ('cybersecurity-analyst','Debugging',84),
  ('cybersecurity-analyst','Stakeholder facilitation',68),
  ('financial-advisor','Financial analysis',84),
  ('financial-advisor','Relationship management',96),
  ('financial-advisor','Regulatory advice',92),
  ('financial-advisor','Client communication',94)
) AS mapping(slug, skill_name, importance)
JOIN occupations occupation ON occupation.slug = mapping.slug
JOIN skills skill ON skill.name = mapping.skill_name
ON CONFLICT (occupation_id, skill_id) DO UPDATE SET importance = EXCLUDED.importance;

INSERT INTO market_signals (occupation_id, country_code, signal_type, value, observed_at, source_id, metadata)
SELECT occupation.id, signal.country_code, 'demand_index', signal.value, DATE '2026-08-20', source.id,
       '{"kind":"phase1_seed","external_ingestion":false}'::jsonb
FROM (VALUES
  ('graphic-designer','IN',54),('graphic-designer','US',58),
  ('software-developer','IN',84),('software-developer','US',80),
  ('accountant','IN',63),('accountant','US',59),
  ('nurse-practitioner','IN',78),('nurse-practitioner','US',93),
  ('aircraft-mechanic','IN',72),('aircraft-mechanic','US',79),
  ('brand-strategist','IN',70),('brand-strategist','US',72),
  ('ux-researcher','IN',80),('ux-researcher','US',84),
  ('cybersecurity-analyst','IN',96),('cybersecurity-analyst','US',94),
  ('financial-advisor','IN',76),('financial-advisor','US',75)
) AS signal(slug, country_code, value)
JOIN occupations occupation ON occupation.slug = signal.slug
CROSS JOIN data_sources source
WHERE source.name = 'Occupation taxonomy demo'
ON CONFLICT (occupation_id, country_code, signal_type, observed_at, source_id) DO NOTHING;

WITH calculated AS (
  SELECT score.id,
    COALESCE((
      SELECT round(sum(task_score.exposure * occupation_task.importance * COALESCE(occupation_task.frequency, 100)) /
                   NULLIF(sum(occupation_task.importance * COALESCE(occupation_task.frequency, 100)), 0), 2)
      FROM occupation_tasks occupation_task
      JOIN LATERAL (
        SELECT exposure FROM task_ai_scores
        WHERE task_id = occupation_task.task_id
        ORDER BY calculated_at DESC LIMIT 1
      ) task_score ON true
      WHERE occupation_task.occupation_id = score.occupation_id
    ), score.ai_exposure) task_exposure,
    COALESCE((
      SELECT round(sum(capability.capability_level * occupation_task.importance * COALESCE(occupation_task.frequency, 100)) /
                   NULLIF(sum(occupation_task.importance * COALESCE(occupation_task.frequency, 100)), 0), 2)
      FROM occupation_tasks occupation_task
      JOIN LATERAL (
        SELECT capability_id FROM task_ai_scores
        WHERE task_id = occupation_task.task_id
        ORDER BY calculated_at DESC LIMIT 1
      ) task_score ON true
      JOIN ai_capabilities capability ON capability.id = task_score.capability_id
      WHERE occupation_task.occupation_id = score.occupation_id
    ), 0) capability_proximity
  FROM occupation_scores score
)
UPDATE occupation_scores score
SET task_exposure = calculated.task_exposure,
    ai_exposure = calculated.task_exposure,
    ai_capability_proximity = calculated.capability_proximity
FROM calculated
WHERE calculated.id = score.id;

UPDATE occupation_scores score
SET replacement_risk = round(
      score.task_exposure * (model.replacement_config->>'task_exposure')::numeric +
      score.ai_capability_proximity * (model.replacement_config->>'ai_capability_proximity')::numeric +
      (100 - score.human_dependency) * (model.replacement_config->>'human_dependency')::numeric +
      (100 - score.physical_dependency) * (model.replacement_config->>'physical_dependency')::numeric +
      score.adoption_pressure * (model.replacement_config->>'adoption_pressure')::numeric +
      (100 - score.market_resilience) * (model.replacement_config->>'market_resilience')::numeric,
      2
    )
FROM scoring_model_versions model
WHERE model.id = score.model_version_id;

ALTER TABLE occupation_scores
  ALTER COLUMN task_exposure SET NOT NULL,
  ALTER COLUMN ai_capability_proximity SET NOT NULL;

CREATE TABLE IF NOT EXISTS score_derivations (
  id BIGSERIAL PRIMARY KEY,
  score_id BIGINT NOT NULL UNIQUE REFERENCES occupation_scores(id) ON DELETE CASCADE,
  occupation_id BIGINT NOT NULL REFERENCES occupations(id) ON DELETE CASCADE,
  model_version_id BIGINT NOT NULL REFERENCES scoring_model_versions(id),
  calculated_total NUMERIC(6,2) NOT NULL,
  factors JSONB NOT NULL,
  task_contributions JSONB NOT NULL DEFAULT '[]'::jsonb,
  input_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS score_derivations_occupation_idx
  ON score_derivations(occupation_id, created_at DESC);

INSERT INTO score_derivations (
  score_id, occupation_id, model_version_id, calculated_total, factors, task_contributions, input_versions, created_at
)
SELECT score.id, score.occupation_id, score.model_version_id, score.replacement_risk,
  jsonb_build_array(
    jsonb_build_object('key','task_exposure','label','Task exposure','rawValue',score.task_exposure,'transformedValue',score.task_exposure,'transformation','identity','weight',(model.replacement_config->>'task_exposure')::numeric,'contribution',round(score.task_exposure * (model.replacement_config->>'task_exposure')::numeric,4)),
    jsonb_build_object('key','ai_capability_proximity','label','AI capability proximity','rawValue',score.ai_capability_proximity,'transformedValue',score.ai_capability_proximity,'transformation','identity','weight',(model.replacement_config->>'ai_capability_proximity')::numeric,'contribution',round(score.ai_capability_proximity * (model.replacement_config->>'ai_capability_proximity')::numeric,4)),
    jsonb_build_object('key','human_dependency','label','Human dependency','rawValue',score.human_dependency,'transformedValue',100-score.human_dependency,'transformation','inverse: 100 - raw','weight',(model.replacement_config->>'human_dependency')::numeric,'contribution',round((100-score.human_dependency) * (model.replacement_config->>'human_dependency')::numeric,4)),
    jsonb_build_object('key','physical_dependency','label','Physical dependency','rawValue',score.physical_dependency,'transformedValue',100-score.physical_dependency,'transformation','inverse: 100 - raw','weight',(model.replacement_config->>'physical_dependency')::numeric,'contribution',round((100-score.physical_dependency) * (model.replacement_config->>'physical_dependency')::numeric,4)),
    jsonb_build_object('key','adoption_pressure','label','Adoption pressure','rawValue',score.adoption_pressure,'transformedValue',score.adoption_pressure,'transformation','identity','weight',(model.replacement_config->>'adoption_pressure')::numeric,'contribution',round(score.adoption_pressure * (model.replacement_config->>'adoption_pressure')::numeric,4)),
    jsonb_build_object('key','market_resilience','label','Market resilience','rawValue',score.market_resilience,'transformedValue',100-score.market_resilience,'transformation','inverse: 100 - raw','weight',(model.replacement_config->>'market_resilience')::numeric,'contribution',round((100-score.market_resilience) * (model.replacement_config->>'market_resilience')::numeric,4))
  ),
  COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
      'taskId', task_row.task_id,
      'task', task_row.task,
      'exposure', task_row.exposure,
      'importance', task_row.importance,
      'frequency', task_row.frequency,
      'normalizedWeight', round(task_row.task_weight / NULLIF(task_row.total_weight,0), 6),
      'exposureContribution', round(task_row.exposure * task_row.task_weight / NULLIF(task_row.total_weight,0), 4)
    ) ORDER BY task_row.importance DESC, task_row.task)
    FROM (
      SELECT task.id task_id, task.name task, latest.exposure,
             occupation_task.importance,
             COALESCE(occupation_task.frequency, 100) frequency,
             occupation_task.importance * COALESCE(occupation_task.frequency, 100) task_weight,
             sum(occupation_task.importance * COALESCE(occupation_task.frequency, 100)) OVER () total_weight
      FROM occupation_tasks occupation_task
      JOIN tasks task ON task.id = occupation_task.task_id
      JOIN LATERAL (
        SELECT exposure FROM task_ai_scores
        WHERE task_id = task.id ORDER BY calculated_at DESC LIMIT 1
      ) latest ON true
      WHERE occupation_task.occupation_id = score.occupation_id
    ) task_row
  ), '[]'::jsonb),
  score.input_versions,
  score.calculated_at
FROM occupation_scores score
JOIN scoring_model_versions model ON model.id = score.model_version_id
ON CONFLICT (score_id) DO UPDATE SET
  calculated_total = EXCLUDED.calculated_total,
  factors = EXCLUDED.factors,
  task_contributions = EXCLUDED.task_contributions,
  input_versions = EXCLUDED.input_versions,
  created_at = EXCLUDED.created_at;

UPDATE score_history history
SET ai_exposure = score.ai_exposure,
    replacement_risk = score.replacement_risk
FROM occupation_scores score
WHERE score.id = history.source_score_id;

COMMIT;
