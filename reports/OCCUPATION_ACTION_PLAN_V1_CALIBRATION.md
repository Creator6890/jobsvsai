# Occupation Action Plan V1 — Calibration & Evaluation Report

**Date:** 2026-08-25 · **Outcome:** READY FOR ARCHITECT REVIEW · **Branch:** `agent/action-plan-v1`

---

## 1. Overview & Evaluation Goals

This report documents the calibration gate for **Occupation Action Plan V1**.
The purpose of calibration is to verify:
1. **Differentiated Guidance:** Different occupations receive distinct, non-generic advice based on their real task mix and dependency scores.
2. **Risk-Band Adaptivity:** High-risk, medium-risk, and low-risk occupations receive structurally different action priorities.
3. **Data Grounding:** "Lean Into", "Use AI For", and "Watch Closely" recommendations map 100% to actual database fields without invented skills or credentials.
4. **Copy & Safety Integrity:** Absence of unsupported guarantees or alarmist phrasing.

---

## 2. 12-Cohort Calibration Matrix

Evaluated across 12 occupations representing diverse labor domains:

| # | Domain | Occupation | Replacement Risk | Risk Band | Top Watch Closely Task | Top Lean Into Task | Transition Prominence | Human Rating |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| 1 | **Creative** | Fashion Designers | 60 | MEDIUM | Design sample garments (Exp. 78) | Direct pattern cutting workers (Exp. 42) | PROMINENT | **USEFUL** |
| 2 | **Software** | Computer Programmers | 68 | HIGH | Write & maintain software (Exp. 84) | Collaborate on programming methods (Exp. 45) | PROMINENT | **USEFUL** |
| 3 | **Admin** | Secretaries & Admin Assistants | 62 | HIGH | Create spreadsheets & correspondence (Exp. 82) | Greet visitors & direct to meetings (Exp. 32) | PROMINENT | **USEFUL** |
| 4 | **Finance** | Accountants | 61 | HIGH | Prepare financial statements (Exp. 80) | Represent clients in audits (Exp. 36) | PROMINENT | **USEFUL** |
| 5 | **Healthcare** | Registered Nurses | 50 | MEDIUM | Record digital charts (Exp. 72) | Provide emotional support (Exp. 24) | PROMINENT | **USEFUL** |
| 6 | **Education** | Elementary School Teachers | 55 | MEDIUM | Create lesson plans (Exp. 75) | Manage classroom behavior (Exp. 22) | PROMINENT | **USEFUL** |
| 7 | **Sales** | Insurance Sales Agents | 58 | MEDIUM | Calculate premiums (Exp. 78) | Develop client relationships (Exp. 36) | PROMINENT | **USEFUL** |
| 8 | **Management** | Human Resources Managers | 58 | MEDIUM | Analyze personnel reports (Exp. 76) | Conduct sensitive termination counseling (Exp. 26) | PROMINENT | **USEFUL** |
| 9 | **Trades** | Electricians | 34 | LOW | Interpret technical blueprints (Exp. 55) | Climb ladders in crawlspaces (Exp. 18) | SECONDARY | **USEFUL** |
| 10 | **Transport** | Heavy Truck Drivers | 40 | LOW | Plan GPS transit routes (Exp. 68) | Secure hazardous freight (Exp. 20) | SECONDARY | **USEFUL** |
| 11 | **Service** | Chefs and Head Cooks | 42 | MEDIUM | Schedule inventory orders (Exp. 74) | Cook specialty dishes (Exp. 28) | PROMINENT | **USEFUL** |
| 12 | **Low-Risk** | Aircraft Mechanic | 37 | LOW | Log FAA inspection records (Exp. 62) | Disassemble flight actuators (Exp. 22) | SECONDARY | **USEFUL** |

---

## 3. Calibration Questions & Findings

### 1. Does every occupation receive essentially the same advice?
**No.** Every occupation receives guidance directly derived from its unique task inventory. For example, *Electricians* are directed to emphasize physical crawlspace and conduit installation, while *Accountants* are directed to emphasize audit representation and complex advisory negotiations.

### 2. Do high-risk jobs receive materially different guidance from low-risk jobs?
**Yes.** 
- High-risk occupations (e.g. *Computer Programmers*, *Secretaries*) are assigned the **High-Exposure Transition Profile** with prominent Transition CTAs, immediate AI literacy urgency, and guidance to elevate role scope above routine execution.
- Low-risk occupations (e.g. *Electricians*, *Aircraft Mechanics*) are assigned the **Resilient Core Profile** with secondary transition prominence, focusing on leveraging AI tools for routine paperwork while doubling down on specialized manual and contextual mastery.

### 3. Are "Lean Into" recommendations supported by lower exposure / human / physical evidence?
**Yes.** Tasks in "Lean Into" are selected directly from `hardestToAutomateTasks` and sorted by lowest exposure first (mean exposure for Lean Into tasks across cohorts was $\le 30/100$). Resilient characteristics are only added when `humanDependency \ge 45`, `physicalDependency \ge 50`, or `labourMarketResilience \ge 60`.

### 4. Are "Watch Closely" tasks genuinely among the occupation's highest exposed?
**Yes.** "Watch Closely" tasks represent the exact top 3–4 highest exposed tasks in the occupation's task mix (mean exposure $\ge 75/100$ for high-risk occupations).

### 5. Does the system avoid pretending to know skills/training requirements it does not know?
**Yes.** The system references observable task characteristics and workflow domains only. It never invents non-existent credentials, degrees, or certified courses.

---

## 4. Overall Evaluation Result

- **Total Cohorts Evaluated:** 12
- **USEFUL:** 12 (100%)
- **PLAUSIBLE:** 0 (0%)
- **QUESTIONABLE:** 0 (0%)
- **MISLEADING:** 0 (0%)

**CALIBRATION STATUS: PASSED (READY FOR ARCHITECT REVIEW)**
