BEGIN;

INSERT INTO data_sources (name, source_url, version) VALUES
  ('Occupation taxonomy demo', 'https://www.onetcenter.org/database.html', 'demo-2026-08'),
  ('JobsVsAI capability evidence', NULL, '1.6.2');

INSERT INTO occupation_categories (slug, name) VALUES
  ('creative-design','Creative & Design'), ('technology','Technology'), ('finance','Finance'),
  ('healthcare','Healthcare'), ('skilled-trades','Skilled Trades'), ('strategy','Strategy'), ('research','Research');

INSERT INTO scoring_model_versions (version, description, exposure_config, replacement_config, is_active) VALUES
  ('JVS 1.0.3', 'Phase 1 explainable scoring model',
   '{"task_automation_exposure":0.45,"ai_capability_proximity":0.15,"human_dependency":0.15,"physical_dependency":0.10,"adoption_pressure":0.10,"market_resilience":0.05}',
   '{"exposure":0.45,"ai_capability_proximity":0.15,"human_dependency":0.15,"physical_dependency":0.10,"adoption_pressure":0.10,"market_resilience":0.05}', true);

INSERT INTO occupations (slug,title,category_id,summary,verdict,source_id) VALUES
('graphic-designer','Graphic Designer',(SELECT id FROM occupation_categories WHERE slug='creative-design'),'AI can automate a large share of production design work. Strategy, taste, client context, and creative direction remain more resilient.','High exposure, but the role is more likely to transform than disappear outright.',1),
('software-developer','Software Developer',(SELECT id FROM occupation_categories WHERE slug='technology'),'AI increasingly accelerates routine coding while system design, product judgment, debugging, and accountability remain human-led.','High task exposure with meaningful demand resilience.',1),
('accountant','Accountant',(SELECT id FROM occupation_categories WHERE slug='finance'),'Transaction processing and routine reporting are highly exposed, while assurance, advisory work, and regulated accountability remain resilient.','Automation pressure is high, especially in routine accounting workflows.',1),
('nurse-practitioner','Nurse Practitioner',(SELECT id FROM occupation_categories WHERE slug='healthcare'),'Clinical decision-making and direct patient care remain strongly human-dependent.','AI will assist this work more than replace it.',1),
('aircraft-mechanic','Aircraft Mechanic',(SELECT id FROM occupation_categories WHERE slug='skilled-trades'),'Work is physically situated, safety-critical, and tightly regulated.','Low replacement risk despite growing diagnostic assistance.',1),
('brand-strategist','Brand Strategist',(SELECT id FROM occupation_categories WHERE slug='strategy'),'Brand strategy shifts value toward commercial judgment, positioning, and stakeholder alignment.','AI assists research and production while strategic accountability remains human-led.',1),
('ux-researcher','UX Researcher',(SELECT id FROM occupation_categories WHERE slug='research'),'Research synthesis is exposed, but human interviewing, trust, and contextual interpretation remain important.','Moderate exposure with relatively low replacement risk.',1),
('cybersecurity-analyst','Cybersecurity Analyst',(SELECT id FROM occupation_categories WHERE slug='technology'),'AI accelerates detection and triage while adversarial judgment and response accountability remain human-led.','Demand resilience and adversarial complexity limit replacement risk.',1),
('financial-advisor','Financial Advisor',(SELECT id FROM occupation_categories WHERE slug='finance'),'AI can automate portfolio analysis, but trust, persuasion, and regulated advice remain human-dependent.','The role will be augmented, with lower replacement risk for relationship-led advisors.',1);

INSERT INTO occupation_scores (occupation_id,model_version_id,ai_exposure,replacement_risk,confidence,trend,human_dependency,physical_dependency,adoption_pressure,market_resilience,salary_potential,future_demand,input_versions)
SELECT o.id, v.id, x.ai_exposure, x.replacement_risk, x.confidence, x.trend, x.human_dependency, x.physical_dependency, x.adoption_pressure, x.market_resilience, x.salary_potential, x.future_demand, '{"occupation":"demo-2026-08","capability":"1.6.2"}'::jsonb
FROM (VALUES
('graphic-designer',84,71,'High','Rising',48,8,89,58,61,54),('software-developer',72,49,'High','Rising',64,4,91,78,86,80),
('accountant',78,63,'High','Rising',57,3,84,65,68,59),('nurse-practitioner',34,22,'High','Stable',94,81,51,92,82,93),
('aircraft-mechanic',29,26,'Medium','Stable',72,96,38,83,73,79),('brand-strategist',52,28,'Medium','Stable',82,4,62,75,71,72),
('ux-researcher',56,24,'High','Stable',88,7,58,81,77,84),('cybersecurity-analyst',64,34,'High','Rising',73,5,80,91,88,94),
('financial-advisor',58,36,'Medium','Stable',89,3,68,76,79,75)
) AS x(slug,ai_exposure,replacement_risk,confidence,trend,human_dependency,physical_dependency,adoption_pressure,market_resilience,salary_potential,future_demand)
JOIN occupations o ON o.slug=x.slug CROSS JOIN scoring_model_versions v WHERE v.is_active;

INSERT INTO tasks (name,description,source_id) VALUES
('Design execution','Produce visual design assets',1),('Image editing & retouching','Edit and enhance images',1),('Layout exploration','Explore composition alternatives',1),('Client communication','Discover and communicate with clients',1),('Strategy & creative direction','Set design strategy and direction',1),
('Boilerplate implementation','Implement routine code patterns',1),('Code documentation','Create technical documentation',1),('System architecture','Design system boundaries',1),('Stakeholder alignment','Align product and engineering decisions',1),
('Transaction classification','Classify financial transactions',1),('Routine reporting','Prepare standard reports',1),('Audit judgment','Evaluate evidence and risk',1),('Client advisory','Provide contextual financial advice',1),
('Clinical documentation','Document patient care',1),('Physical examination','Examine patients in person',1),('Patient care planning','Develop contextual care plans',1),
('Diagnostic review','Review technical diagnostic evidence',1),('Physical repair','Repair equipment in the physical world',1),('Safety sign-off','Accept responsibility for safe operation',1),
('Research synthesis','Synthesize user and market research',1),('Interview facilitation','Conduct contextual human interviews',1),('Incident response','Coordinate response to security incidents',1),('Relationship advice','Provide trusted client guidance',1);

INSERT INTO ai_capabilities (slug,name,description,capability_level,evidence,version,source_id) VALUES
('general-digital-work','General digital knowledge work','Text, image, code, and structured-data assistance',88,'[]','1.6.2',2);

INSERT INTO occupation_tasks (occupation_id,task_id,importance,frequency,is_resilient)
SELECT o.id,t.id,x.importance,x.frequency,x.resilient FROM (VALUES
('graphic-designer','Design execution',95,90,false),('graphic-designer','Image editing & retouching',92,80,false),('graphic-designer','Layout exploration',76,70,false),('graphic-designer','Client communication',68,60,true),('graphic-designer','Strategy & creative direction',89,55,true),
('software-developer','Boilerplate implementation',65,80,false),('software-developer','Code documentation',60,65,false),('software-developer','System architecture',92,45,true),('software-developer','Stakeholder alignment',78,55,true),
('accountant','Transaction classification',90,78,false),('accountant','Routine reporting',88,72,false),('accountant','Audit judgment',92,56,true),('accountant','Client advisory',70,45,true),
('nurse-practitioner','Clinical documentation',65,75,false),('nurse-practitioner','Physical examination',96,88,true),('nurse-practitioner','Patient care planning',94,82,true),
('aircraft-mechanic','Diagnostic review',88,62,false),('aircraft-mechanic','Physical repair',98,92,true),('aircraft-mechanic','Safety sign-off',98,80,true),
('brand-strategist','Research synthesis',72,64,false),('brand-strategist','Stakeholder alignment',92,75,true),('brand-strategist','Strategy & creative direction',96,82,true),
('ux-researcher','Research synthesis',82,78,false),('ux-researcher','Interview facilitation',95,85,true),('ux-researcher','Stakeholder alignment',88,70,true),
('cybersecurity-analyst','Diagnostic review',85,75,false),('cybersecurity-analyst','Incident response',96,68,true),
('financial-advisor','Routine reporting',55,50,false),('financial-advisor','Relationship advice',96,82,true),('financial-advisor','Client advisory',92,75,true)
) AS x(slug,task,importance,frequency,resilient) JOIN occupations o ON o.slug=x.slug JOIN tasks t ON t.name=x.task;

INSERT INTO task_ai_scores (task_id,capability_id,exposure,confidence)
SELECT t.id,c.id,x.exposure,85 FROM (VALUES
('Design execution',92),('Image editing & retouching',90),('Layout exploration',79),('Client communication',31),('Strategy & creative direction',27),
('Boilerplate implementation',88),('Code documentation',82),('System architecture',38),('Stakeholder alignment',24),
('Transaction classification',91),('Routine reporting',86),('Audit judgment',41),('Client advisory',29),
('Clinical documentation',76),('Physical examination',11),('Patient care planning',23),('Diagnostic review',51),('Physical repair',8),('Safety sign-off',5),
('Research synthesis',72),('Interview facilitation',18),('Incident response',25),('Relationship advice',20)
) AS x(task,exposure) JOIN tasks t ON t.name=x.task CROSS JOIN ai_capabilities c WHERE c.slug='general-digital-work';

INSERT INTO career_relationships (source_occupation_id,target_occupation_id,relationship_type,skill_overlap,transition_difficulty,retraining_months,fit_score,model_version_id)
SELECT source.id,target.id,'adjacent',x.overlap,x.difficulty,x.months,x.fit,v.id FROM (VALUES
('graphic-designer','brand-strategist',82,'Easy–Moderate','3–6 months',91),('graphic-designer','ux-researcher',67,'Moderate','6–12 months',86),
('software-developer','cybersecurity-analyst',74,'Moderate','6–12 months',89),('accountant','financial-advisor',72,'Moderate','6–12 months',83)
) x(source_slug,target_slug,overlap,difficulty,months,fit) JOIN occupations source ON source.slug=x.source_slug JOIN occupations target ON target.slug=x.target_slug CROSS JOIN scoring_model_versions v WHERE v.is_active;

COMMIT;
