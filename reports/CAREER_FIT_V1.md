# Career Fit V1 — Ability Assessment & Career Intelligence Recommendation

**Product Feature Design, Implementation, and Evaluation Report**  
**Author:** Worker B (Antigravity)  
**Date:** 2026-08-25  
**Branch:** `agent/ability-assessment-v1`  
**Status:** READY FOR ARCHITECT REVIEW  

---

## 1. Product Concept & Positioning

**Career Fit** (`/career-fit`) is an independent career-intelligence discovery layer designed for users who:
- Are starting their careers and do not know which specific job title to search for.
- Are actively contemplating a career pivot or upskilling transition.
- Want an objective, evidence-based understanding of which professional occupations align naturally with their core work-strengths and problem-solving preferences.

### Distinction from Personality Quizzes
Career Fit is explicitly positioned as a **career-intelligence tool**, not a personality test or psychological diagnostic:
- **No Pseudo-Scientific Types**: We do not assign users 4-letter type codes or personality labels.
- **Behavioral & Competency-Focused**: The assessment evaluates concrete, observable problem-solving behaviors, technical affinities, communication styles, and operational preferences.
- **Output Framing**: Results are presented as a **"Work-Strength Profile"** with qualitative strength bands (*Developing*, *Moderate*, *High*, *Very High*).
- **Core Value Proposition**: Users discover which careers suit their capabilities, paired immediately with JobsVsAI's verified **AI Exposure** and **Replacement Risk** scores.

---

## 2. Assessment Dimensions

The V1 assessment evaluates **8 interpretable work-strength dimensions** grounded in standard O*NET occupational taxonomies and modern workplace competencies:

| Dimension Key | Dimension Label | Core Behavioral Focus | O*NET / Workplace Mapping |
| :--- | :--- | :--- | :--- |
| **`analytical`** | **Analytical Reasoning** | Systematic problem solving, quantitative reasoning, empirical data evaluation, logic. | Critical Thinking, Complex Problem Solving, Science, Mathematics |
| **`creativity`** | **Creativity & Innovation** | Novel concept synthesis, visual/spatial expression, generative ideation, open-ended design. | Originality, Fluency of Ideas, Visualization, Design |
| **`communication`** | **Communication & Expression** | Articulating specialized concepts, writing reports, public speaking, storytelling. | Written Expression, Speaking, Active Listening, Reading Comprehension |
| **`people`** | **People & Interpersonal** | Empathy, counseling, client care, mentoring, conflict mediation, human connection. | Social Perceptiveness, Service Orientation, Negotiation, Counseling |
| **`practical`** | **Practical & Hands-On** | Physical tool manipulation, equipment operation, spatial assembly, outdoor craft. | Equipment Maintenance, Manual Dexterity, Physical Inspection |
| **`organization`** | **Organization & Structure** | Operational rigor, compliance, scheduling, error checking, process management. | Quality Control Analysis, Monitoring, Administration, Attention to Detail |
| **`technology`** | **Technology Affinity** | Digital systems, programming, automation tools, software architecture, technical workflows. | Programming, Systems Analysis, Technology Design, Automation |
| **`leadership`** | **Leadership & Strategy** | Strategic direction, high-stakes decision-making, team coordination, resource allocation. | Judgment and Decision Making, Management of Personnel Resources |

---

## 3. Question Structure & Design

The assessment consists of **20 original, concise questions** designed for quick completion (~3–5 minutes).

### Key Design Principles:
1. **Original Question Authoring**: No proprietary psychometric inventory questions were copied.
2. **Obfuscated Career Targets**: Questions describe direct task behaviors rather than revealing specific job titles (e.g., asking about physical repair rather than "Do you want to be an electrician?").
3. **Primary + Secondary Weighting**: Each question has a primary dimension (weight `1.0`) and selective secondary cross-dimensional weights (`0.3`–`0.4`) to capture nuanced work styles.
4. **5-Point Response Scale**:
   - `1`: Strongly disagree
   - `2`: Disagree
   - `3`: Neutral
   - `4`: Agree
   - `5`: Strongly agree

### Full Question Registry:
1. *Analytical*: "I enjoy breaking complicated problems down into smaller, logical parts to find a solution."
2. *Creativity*: "I would rather create an original design or concept than follow an established template."
3. *People*: "I get energized by directly helping, supporting, or counseling people with their needs."
4. *Practical*: "I prefer hands-on work where I interact with physical equipment, tools, or tangible materials."
5. *Technology (Sec: Analytical)*: "I am naturally drawn to experimenting with new software, coding tools, or digital systems."
6. *Communication*: "I feel confident explaining technical or difficult concepts in simple terms to different audiences."
7. *Organization*: "I thrive when organizing workflows, tracking detailed schedules, and ensuring consistent accuracy."
8. *Leadership*: "I am comfortable making decisions under uncertainty and taking responsibility for project outcomes."
9. *Analytical*: "I naturally search for empirical patterns, data trends, and hard evidence before making a judgment."
10. *Creativity*: "I enjoy reimagining how products, spaces, narratives, or visual presentations look and work."
11. *People (Sec: Communication)*: "I am attentive to other people's emotions, motivations, and unspoken concerns during conversations."
12. *Practical*: "I find it deeply satisfying to assemble, repair, or inspect physical objects to see how they function."
13. *Technology*: "I like understanding how digital architectures, networks, or automated workflows operate behind the scenes."
14. *Communication*: "I enjoy writing structured articles, reports, or presentations designed to persuade or educate readers."
15. *Organization*: "I take pride in spotting subtle errors, adhering to quality standards, and maintaining structured records."
16. *Leadership*: "I naturally step forward to coordinate people, establish priorities, and delegate tasks when a project stalls."
17. *Analytical (Sec: Practical)*: "I find it engaging to investigate why a process or machine is failing and devise a systematic fix."
18. *Creativity (Sec: Analytical)*: "I am energized by open-ended problems that have multiple valid creative pathways rather than one formula."
19. *People (Sec: Leadership)*: "I prefer roles where building personal trust, mentoring, or collaborating with colleagues is central to the job."
20. *Organization (Sec: Leadership)*: "I enjoy managing timelines, budgets, and operational deliverables to ensure projects finish on target."

---

## 4. Deterministic Scoring Algorithm

The assessment scoring algorithm is 100% deterministic, inspectable, and reproducible without server dependencies or LLMs.

### Mathematical Formulation:

1. **Normalized Question Score**:
   $$s_i = \frac{r_i - 1}{4} \in [0.0, 1.0] \quad \text{for } r_i \in \{1, 2, 3, 4, 5\}$$
   *(Unanswered questions default gracefully to neutral $r_i = 3 \implies s_i = 0.5$)*.

2. **Dimension Score Calculation**:
   For each dimension $d \in \{\text{analytical}, \dots, \text{leadership}\}$:
   $$\text{Score}(d) = \text{round}\left( \frac{\sum_{i} w_{i,d} \cdot s_i}{\sum_{i} w_{i,d}} \times 100 \right) \in [0, 100]$$

3. **Qualitative Strength Bands**:
   - **80–100**: *Very High* (Distinctive core strength)
   - **60–79**: *High* (Active competency)
   - **40–59**: *Moderate* (Balanced capability)
   - **0–39**: *Developing* (Low self-reported preference)

---

## 5. Occupation Matching Method

### Occupational Vector Construction:
Every occupation in the JobsVsAI database (507 published roles) is mapped to an 8-dimensional reference vector $\mathbf{V}_{\text{occ}} \in [0, 100]^8$ derived deterministically from:
1. **Category Archetype Baseline**: SOC Major Group baseline values (e.g. *Computer & Mathematical* baseline is high in technology/analytical; *Healthcare* is high in people/analytical).
2. **Structural Modifier Calibration**:
   - $\text{practical} = 0.40 \times \text{baseline} + 0.60 \times \text{physicalDependency}$
   - $\text{people} = 0.45 \times \text{baseline} + 0.55 \times \text{humanDependency}$
   - $\text{communication} = 0.55 \times \text{baseline} + 0.45 \times \text{humanDependency}$
3. **Specialized Title Refinements**: Title-level adjustments for specialized sub-disciplines (e.g., data scientists, designers, managers, therapists, software engineers).

### Compatibility Metric (Career Fit %):
Let $\mathbf{U} = (u_1, \dots, u_8)$ be the user profile vector and $\mathbf{O} = (o_1, \dots, o_8)$ be the occupation vector.
We compute a weighted root-mean-square distance emphasizing dimensions where the user scored High/Very High ($u_d \ge 60$, weight factor $1.6\times$):

$$\text{MSE} = \frac{\sum_{d=1}^8 \alpha_d \cdot (u_d - o_d)^2}{\sum_{d=1}^8 \alpha_d}, \quad \text{where } \alpha_d = \begin{cases} 1.6 & \text{if } u_d \ge 60 \\ 1.0 & \text{otherwise} \end{cases}$$

$$\text{RMS} = \sqrt{\text{MSE}}$$

$$\text{Career Fit} = \max\left(10, \min\left(99, \text{round}\left(100 - \frac{\text{RMS}}{55} \times 100\right)\right)\right)$$

### Explanations & Considerations:
- **`whyFit`**: Synthesizes the highest overlapping competencies between the user and the role (e.g., *"Strong alignment with your profile in Analytical Reasoning and Technology Affinity."*).
- **`considerations`**: Automatically tags physical demands, heavy relational requirements, high AI exposure factors, or strong automation resilience from underlying structural indicators.

---

## 6. Existing APIs & Data Reused

The integration reuses existing JobsVsAI data structures with **zero duplication**:
1. **`getOccupations()`**: Fetches the 507 published occupations via `/api/v1/occupations`.
2. **`Occupation` schema**: Directly utilizes `title`, `slug`, `category`, `aiExposure`, `replacementRisk`, `humanDependency`, `physicalDependency`, and `tasks`.
3. **Existing Routing**: Recommends direct links to `/jobs/[slug]`.
4. **Existing Design System**: Uses standard CSS variables (`--card`, `--soft`, `--violet`, `--line`, `.chip`, `.score-badge`, `.button`, `.container`).

---

## 7. Backend Requirements Assessment

**Verdict: NO NEW BACKEND ENDPOINT REQUIRED FOR V1.**

- The existing public `/occupations` endpoint already provides sufficient structural and category signal (`humanDependency`, `physicalDependency`, `category`, `aiExposure`, `replacementRisk`).
- Full client-side matching runs instantaneously (< 5ms) for all 507 occupations.
- No heavy database computations or backend migrations were needed.

---

## 8. User Interface & Experience Flow

```
1. /career-fit Landing
   └── Hero title + 3-5 min explanation + 8 dimension preview + "Begin Assessment" CTA
2. Step-by-Step Questionnaire
   └── Question count (1-20) + Progress bar + Large 5-point touch buttons + Auto-advance
3. Results & Profile Dashboard
   ├── Your Work-Strength Profile (Headline, narrative, 8 horizontal strength bars with qualitative badges)
   ├── Best Career Matches Grid (8-12 cards with Career Fit %, AI Exposure, Replacement Risk, Why it fits, Considerations)
   ├── Sorting Controls (Best Career Fit / Lowest Replacement Risk / Lowest AI Exposure)
   └── Interpretation & Transition Guidance Card
```

---

## 9. Responsive QA & Mobile-First Validation

Tested across standard responsive viewport widths:
- **360px & 390px (Mobile portrait)**: Question options render as full-width tap targets (min-height 52px); progress indicator is pinned cleanly; results stack vertically without horizontal scroll.
- **768px (Tablet / iPad portrait)**: Strength grid formats in 2 clean columns; match cards render in a responsive 2-column layout.
- **1024px & 1440px (Desktop / Wide)**: Multi-column grid for strength bars and recommendations; filter pills align adjacent to the section heading.

---

## 10. Test Coverage & Verification

Executed via Node.js native test runner (`npm test`):
- **Total Frontend Tests**: **26/26 passing** (13 AdSense tests + 13 Career Fit tests).
- **Key Test Cases**:
  1. *Assessment structure*: Exactly 20 questions mapping to all 8 dimensions.
  2. *Determinism*: Identical answers strictly produce identical profile vectors and match rankings.
  3. *Boundary conditions*: All 1s -> 0/100 ("Developing"); All 5s -> 100/100 ("Very High"); All 3s -> 50/100 ("Moderate").
  4. *Missing/partial responses*: Default safely to neutral 50 without error.
  5. *Vector derivation*: All derived occupation dimensions bounded between 0 and 100.
  6. *Domain accuracy*: Tech answers rank *Software Developer* highest; Caregiving answers rank *Registered Nurse* highest.
  7. *Fit bounds*: Career Fit scores stay bounded [10%..99%].
  8. *Sorting safety*: Re-sorting by "Lowest Replacement Risk" and "Lowest AI Exposure" works correctly.
  9. *Score isolation*: Verifies `aiExposure` and `replacementRisk` on the matched occupations are strictly untouched.
  10. *Navigation integrity*: Verified `SiteHeader.tsx`, `SiteFooter.tsx`, and `page.tsx` links.

---

## 11. Known Limitations of V1

1. **Self-Reported Data**: Results reflect user self-assessment rather than verified skill testing.
2. **Cohort Scope**: Recommendations are drawn from JobsVsAI's 507 published launch occupations.
3. **No Dynamic Compensation Filtering**: Salary filters are excluded in V1 in accordance with Phase 5 production score store policies.

---

## 12. V2 Recommendations (Future Enhancements)

1. **Shareable Result Tokens**: Implement a deterministic, lightweight base64 URL hash (e.g. `/career-fit?p=A85C70...`) so users can bookmark and share their profile without database storage.
2. **Compare Integration**: Add a direct "Compare with my current job" action from the Career Match card to `/compare/[slug1]-vs-[slug2]`.
3. **Granular Skill-Gap Mapping**: Ingest O*NET detailed work activities (DWAs) to display specific transferable vs. gap skills when clicking a matched career.

---

## Final Status

**READY FOR ARCHITECT REVIEW**
- **Branch:** `agent/ability-assessment-v1`
- **Frontend Tests:** 26/26 passing
- **Lint:** 0 errors, 0 warnings
- **Build:** Clean standalone Next.js 16 build with `/career-fit` compiled
