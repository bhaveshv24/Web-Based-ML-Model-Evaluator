# TSMP-21 - USA-01 usability study protocol (NFR-005)

**Status: prepared, NOT EXECUTED.** No session has been run and no result exists. The study is
blocked by DEF-07: the MLE-17 React SPA, which the primary task runs through, does not exist.
Run it only after MLE-17 is delivered and meets the entry criteria below.

| Item | Value |
|---|---|
| Requirement | NFR-005: "A first-time user shall complete a first evaluation (upload, validate, run, view) in no more than 5 primary screens." SRS method: usability walkthrough |
| STP case | USA-01: "Five new users complete first evaluation". Expected: "At most 5 primary screens; issues logged" |
| STP strategy | Task-based walkthrough with five first-time users; observation sheet; owners M2 and M4 |
| Design reference | SAD 8: Register → Login → New Evaluation → Dashboard (4 primary screens) |
| Materials | This protocol; [observation sheet](usability/USA-01_OBSERVATION_SHEET.md); [results template](usability/usa01-results-template.csv); [issue log template](usability/usa01-issues-template.csv); participant kit from `scripts/validation/usability/make_kit.py` |

## 1. Acceptance rule (unchanged from the STP)

USA-01 **passes** only when all of the following are true:

1. Five first-time participants each attempt scenario S1.
2. Every participant completes S1: they see the metrics of their own evaluation on the
   dashboard.
3. Every participant's S1 path uses **at most 5 primary screens** (counting rule in section 3).
4. Every issue observed is logged in the issue log.

If any participant fails S1 or needs more than 5 primary screens, USA-01 **fails**. Every
issue that caused it is raised as a defect in `TSMP-21_DEFECT_REGISTER.md`, using STP Part C
section 12 severities. Scenarios S2-S5 are diagnostic. They produce issues but do not change the
USA-01 verdict.

**Assistance rule (decided before the sessions, so it cannot be argued afterwards).** The
facilitator may only use the scripted prompts in section 5. Any other help counts as an
assist. A participant who needs an assist on S1 has **not completed** S1. The team should
confirm this rule before the first session. If the team wants a different rule, record the
change and its date here *before* any session runs.

## 2. Entry criteria

| # | Criterion | How to check |
|---|---|---|
| E1 | MLE-17 delivered: UI-01 register/login, UI-02 upload wizard, UI-03 run status, UI-05 dashboard reachable in the browser | Facilitator dry run of S1 |
| E2 | The ST-AUTH-01, ST-ING-01 and ST-EXE-01 UI system tests have been rerun and pass | Execution report section 3 |
| E3 | Stack deployed with `docker compose up` and healthy | `python scripts/validation/portability_check.py` preflight PASS |
| E4 | Participant kit generated and checksummed | `make_kit.py --out <kit>`; `SHA256SUMS` identical for every participant |
| E5 | Pilot session with one person who is not a participant, then protocol fixes | Pilot notes kept, not counted |
| E6 | Five participants recruited and consented (section 4) | Consent forms on file (not in the repository) |

## 3. Counting primary screens

A **primary screen** is a distinct full page view of the application that the participant
reaches on the path to the goal. One screen is counted for each *distinct* screen visited
during S1, from the first page the participant opens to the dashboard that shows their metrics.

| Counts as one primary screen | Does not count |
|---|---|
| Each distinct UI-xx screen (for example UI-01 register, UI-01 login, UI-02 wizard, UI-03 run status, UI-05 dashboard), or each distinct route if the SPA has more screens than the SAD lists | Steps inside one screen (the three UI-02 wizard steps are one screen) |
| A screen the participant reaches by mistake or a detour (wrong menu item) | Modals, toasts, inline validation messages, tooltips |
| | The operating system's file picker |
| | Returning to a screen already counted |

Record the ordered list of screen IDs on the observation sheet. The count is the number of
distinct IDs in that list. Both the ordered path and the distinct count go into the results
file, so the count can be re-checked.

The facilitator records which screens exist in the build under test, with their routes, before
the first session (observation sheet, part A).

## 4. Participants

- **Number:** five. The pilot participant is not one of them.
- **Profile:** the SRS "User" class (ML student or researcher, technically capable). Each
  participant must have trained a scikit-learn model before. They must not have seen or used
  this application, its documentation or its source code. Team 13 members are excluded.
- **Identity:** use codes P1-P5 only. Names, emails and recordings are not committed to the
  repository. Each participant registers with a study address the facilitator provides, for
  example `usa01-p1@<domain>`, and a password they choose.
- **Consent:** written consent to observation, note-taking and (optional) screen recording,
  with the right to stop at any time.

## 5. Session procedure (about 30 minutes)

1. **Set-up (facilitator, before the participant arrives).** Open a fresh browser profile
   (Chrome) at the application's start URL. Put the kit folder on the desktop. Start the timer
   sheet and, with consent, the screen recording.
2. **Briefing (read verbatim):** "We are testing the application, not you. Please think aloud
   as you work. I can't help with the tasks, but you can ask me to repeat a task card. Stop
   whenever you like."
3. **Scenarios.** Hand over one task card at a time (section 6). Start the clock when the card
   is handed over. Stop it when the success condition is met, or when the participant gives up
   or 10 minutes pass.
4. **Allowed prompts (not assists):** "What would you try next?", "Please keep thinking
   aloud.", re-reading the task card. Anything else is an assist and is logged.
5. **After each scenario:** ask the Single Ease Question: "Overall, how easy or difficult was
   this task?" on a scale of 1 (very difficult) to 7 (very easy).
6. **After all scenarios:** the 10-item System Usability Scale (observation sheet, part D).
7. **Debrief:** "What was most confusing?" Then thank the participant. Delete the browser
   profile.

## 6. Scenarios

Task cards give the goal, never the clicks. Kit files are named as in `make_kit.py`.

| ID | Task card (read to participant) | Requirements | Success condition | Measures |
|---|---|---|---|---|
| **S1 (scored)** | "You trained `iris_random_forest.pkl` on `iris.csv`. Create an account, then find out how accurate the model is on that dataset." | NFR-005; FR-001, FR-002, FR-008..FR-022 | The dashboard shows the metrics (accuracy and confusion matrix) of this model and dataset | Completed (Y/N), assists, distinct primary screens, ordered path, time, errors, SEQ |
| S2 | "Try evaluating the same model on `wine.csv` instead. What happens, and why?" | FR-012, FR-013 | The participant reports the feature mismatch (the model expects 4 features, the file has 13) in their own words | Completed, time, errors, SEQ, participant's explanation |
| S3 | "Evaluate `iris_logistic_regression.joblib` and `iris_decision_tree.pkl` on `iris.csv` too. Which of the three models is best, and save a PDF report of the comparison." | FR-023, FR-024, FR-026, FR-027 | The participant names the best model per the comparison and saves a PDF that opens | Completed, time, errors, SEQ |
| S4 | "Find your failed or rejected attempts in your history and delete one evaluation you no longer need." | FR-005, FR-006 | History filtered by status; one evaluation deleted and gone from the list | Completed, time, errors, SEQ |
| S5 | "You're done. Make sure nobody else using this computer can see your results." | FR-003 | Signed out; protected pages not visible after reload | Completed, time, SEQ |

S2 depends on S1 and S3 depends on S1. If S1 fails, give S2-S5 anyway for diagnostic data, but
the facilitator may set up the precondition (logged as "facilitator setup", not an assist).

## 7. Data recording

- One observation sheet per participant ([USA-01_OBSERVATION_SHEET.md](usability/USA-01_OBSERVATION_SHEET.md)),
  filled in during the session.
- After the session, transfer it to one row per participant and scenario in
  usa01-results.csv (created after the sessions), copied from [the template](usability/usa01-results-template.csv).
- Log every issue in usa01-issues.csv (created after the sessions), copied from [the template](usability/usa01-issues-template.csv).
  Raise every issue at severity Medium or above as a defect in `TSMP-21_DEFECT_REGISTER.md`.
- Commit the two completed CSV files to `docs/evidence/tsmp-21/usa01/`. Keep paper sheets,
  consent forms and recordings off the repository.

## 8. Analysis and reporting

1. For S1, per participant: completed (Y/N), assists, distinct primary screens. USA-01 verdict
   by the rule in section 1.
2. Descriptive statistics only (five participants): per-scenario completion count, median and
   range of time, median SEQ, and the SUS score per participant and its mean (standard SUS
   scoring: odd items score − 1, even items 5 − score, sum × 2.5).
3. Update the USA-01 row of `TSMP-21_TEST_EXECUTION_REPORT.md` (section 3.6) with the actual
   result and Pass/Fail. Update the NFR-005 row of the RTM: source = the MLE-17 screens, test =
   USA-01, status by the RTM status rule. Update section 6 of the validation report.
4. Run `python scripts/validation/check_rtm.py` before committing.

## 9. Change log

| Date | Change |
|---|---|
| 6 November 2026 | Protocol, observation sheet, templates and kit generator prepared (TSMP-21). Not executed: blocked by DEF-07 |
