# Team 13 sprint retrospectives

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.

Prepared by Bhavesh Velluru, 9 November 2026. Reconstructed from repository commits, PRs, backlog and execution reports. These are evidence-based retrospective drafts for team review; no meeting attendance, quotes or team agreement is asserted.

The course delivery windows and actual merge dates differ. Preserve the real Git dates in submission evidence. The six iterations in the approved baseline were grouped into three delivery sprints in JIRA_BACKLOG.md.

## Sprint 1 - MLE-01..08
### Delivered and evidence
Foundation, CI, Docker topology, authentication, history/workspaces and input validation. Repository history starts documentation upload on 3 October and implementation commits on 13 October. Tests in `test_auth_history_workspaces.py`, `test_ingestion.py` and `test_ingestion_api.py` cover the increment.
### What worked
Complete functional ownership made auth, ingestion, execution and reporting responsibilities explicit. Automated API and boundary checks provided a repeatable baseline for subsequent work.
### Impediments and carry-over
Compatibility inspection depended on the later execution sandbox; early code had to fail closed until that integration existed. The course-required Sprint 1 video needs a repository/link check before submission.
### Proposed improvement and follow-up
M2 and M3 should agree on compatibility contracts before parallel implementation. Each owner should attach the tests, review and demo evidence to the story when it closes. Confirm these actions at team review.

## Sprint 2 - MLE-09..16
### Delivered and evidence
PR #29 integrated asynchronous sandboxed evaluation and metrics. PR #30 integrated dashboards, guarded comparison and report exports. Both merge commits are dated 4 November. SPRINT_2_EVIDENCE.md records 273 passed tests and 96.17% backend coverage, real containment checks, browser `/results` checks and a Compose smoke run.
### What worked
Trusted metrics were cross-checked with scikit-learn. Hostile models, cleanup behavior and report parsing were exercised alongside normal flows. Browser testing found issues that API-only checks could miss.
### Impediments and carry-over
The evidence records a Celery/Kombu/Redis compatibility problem and root-owned media volume during startup; these were corrected and retried. The full React registration/upload workflow remained in MLE-17. The course-required Sprint 2 video needs a final link check.
### Proposed improvement and follow-up
M3 should retain compatible dependency bounds and test queue shutdown. All owners should run the Compose smoke path early. Bidre (TSMP-17), with Bhavesh reviewing result/report contracts, should verify the complete browser workflow before the next release review.

## Sprint 3 - MLE-17..22
### Delivered and evidence
React routes and security work merged in PR #31 (7 November). Retention and performance gates merged in PR #32 (9 November). Validation tools, defect records and RTM work merged in PR #33 (9 November, baseline 3f11b12). The integration fix reconciled four conflicts and replaced two hardcoded weak test inputs with generated values.
### What worked
Earlier integration results (385 pass, 9 Docker skips, 7 expected failures) are historical. Final required-infrastructure execution passed 416 tests with no skips/expected failures, 97.36% backend lines and 92.67% branch destinations. The final Chrome flow passed 11 scenarios. RTM checks validate 48 requirement references.
### Impediments and carry-over
Evaluator access, shared-input cleanup, HTTPS and the Sonar gate were corrected and verified. ADMIN hierarchy remains an explained design deviation. Five first-time participant sessions and complete Windows/current browser evidence remain pending. Final local changes have not been pushed, so final remote CI has not run.
### Proposed improvement and follow-up
Bidre owns TSMP-17/18 workflow/security coordination, Anand TSMP-19/20 performance/platform/quality evidence, Ayush TSMP-21/22 execution/RTM, and Bhavesh TSMP-23/24 packaging/governance. Collect actual participant and platform evidence, review deviations as a team, and preserve historical dates and individual reviews. Videos are a separate team deliverable.

## Final review record
Team review and acceptance of these reconstructed retrospectives remain to be recorded by the team. Add the actual review date, participants and decisions after that review. Use issue comments or a follow-up commit so evidence remains traceable.
