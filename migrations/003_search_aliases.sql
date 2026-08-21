BEGIN;

ALTER TABLE occupations ADD COLUMN IF NOT EXISTS search_aliases TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS occupations_search_text_trgm_idx
  ON occupations USING gin (lower(title || ' ' || search_aliases) gin_trgm_ops);

UPDATE occupations SET search_aliases = CASE slug
  WHEN 'software-developer' THEN 'software engineer embedded software engineer software QA engineer programmer coding developer'
  WHEN 'graphic-designer' THEN 'visual designer communication designer production designer'
  WHEN 'accountant' THEN 'accounting auditor bookkeeper financial accountant'
  WHEN 'nurse-practitioner' THEN 'advanced practice nurse clinical nurse healthcare'
  WHEN 'aircraft-mechanic' THEN 'aviation mechanic aircraft maintenance technician'
  WHEN 'brand-strategist' THEN 'brand planner brand consultant positioning strategist'
  WHEN 'ux-researcher' THEN 'user experience researcher user researcher design researcher'
  WHEN 'cybersecurity-analyst' THEN 'security analyst information security analyst SOC analyst'
  WHEN 'financial-advisor' THEN 'financial planner wealth advisor investment advisor'
  ELSE search_aliases
END;

COMMIT;
