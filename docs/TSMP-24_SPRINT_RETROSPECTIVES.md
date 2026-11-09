# Team 13 sprint retrospectives
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
M3 should retain compatible dependency bounds and test queue shutdown. All owners should run the Compose smoke path early. M2/M4 should verify the complete browser workflow before the next release review.

## Sprint 3 - MLE-17..22
### Delivered and evidence
React routes and security work merged in PR #31 (7 November). Retention and performance gates merged in PR #32 (9 November). Validation tools, defect records and RTM work merged in PR #33 (9 November, baseline 3f11b12). The integration fix reconciled four conflicts and replaced two hardcoded weak test inputs with generated values.
### What worked
Independent security, Docker, Compose and cross-OS tooling checks made failures specific. The RTM checker catches broken source/test/evidence references. The 9 November local integration run passed 385 cases with 97.34% backend line coverage, 9 Docker skips and 7 expected failures.
### Impediments and carry-over
The 6 November validation reports still describe the UI as absent. A later merge supplies the frontend, so the original UI cases and usability study need retest before statuses change. Expected failures preserve evaluator/ADMIN/HTTPS gaps. Windows Compose and availability evidence remain subject to the recorded environment and observation-window requirements. Full Part 3 report generation is the next activity.
### Proposed improvement and follow-up
Ayush and Bhavesh should reconcile the RTM and validation report against the final commit. M2/M4 should collect the original browser cases and real participant evidence. All owners should preserve exact CI runs and distinguish infrastructure skips from successful executions. Team review should resolve policy/deployment deviations and confirm final submission readiness.

## Final review record
Team review and acceptance of these reconstructed retrospectives remain to be recorded by the team. Add the actual review date, participants and decisions after that review. Use issue comments or a follow-up commit so evidence remains traceable.
