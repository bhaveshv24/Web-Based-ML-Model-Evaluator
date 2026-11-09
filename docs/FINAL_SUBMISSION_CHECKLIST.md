# Final submission checklist

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.

Team 13 | Updated 9 November 2026 | Implementation revision `3f96c54` and final source manifest

This is the current audit against 01FAQs_MiniProjectDemo.pdf, 02TheCheckList.pdf and the
Part 1-3 handouts. PASS means evidence is present. TEAM ACTION identifies evidence that
requires the real team, participants, a platform host or an actual recording.

| Requirement | Status | Evidence / next action |
| --- | --- | --- |
| SRS with measurable FR/NFR/security requirements and use case diagram | PASS | Approved combined PDF plus FINAL_SRS_SAD_STP_UPDATE.md |
| SAD with components, security architecture, API/error design and two sequences | PASS | Approved combined PDF and updated deployment/API amendment |
| Test Plan strategy/environment/criteria, traceability and security Section 5.1 | PASS | Original Part C plus explicit Section 5.1 of final amendment |
| Updated original test cases | PASS | FINAL_TEST_CASES.md retains 80 original IDs and records partial/blocked items |
| Unit Test Report | PASS | UNIT_TEST_REPORT.md and PDF; 121 dedicated unit/service cases pass |
| System Validation Report | PASS | SYSTEM_VALIDATION_REPORT.md and PDF; live system and browser evidence |
| Code Coverage Report | PASS | CODE_COVERAGE_REPORT.md and PDF; backend lines 97.36% |
| Branch Coverage Report | PASS | BRANCH_COVERAGE_REPORT.md and PDF; backend destinations 92.67% |
| Full automated regression | PASS | 416 pass; zero failures, skips or expected failures |
| CI, dependency/static checks and real sandbox tests | PASS locally; remote run pending | Workflow and final raw outputs; changes remain local at the user’s request, so final remote CI has not run |
| SonarQube quality gate | OK | Final sonar JSON/log; gate enforces zero blocker/critical findings |
| GitHub backlog ownership | PASS | Read-only audit found all 24 issues assigned and closed; actual closure alone does not prove validation |
| Linked project, story points and sprint fields | TEAM ACTION | Confirm the live GitHub/Jira board shows the course-required estimates and sprint assignments |
| Individually raised PRs and owner reviews | TEAM ACTION | Show each member's actual PR/review/commit history in the viva |
| One-minute Sprint 1 and two-minute Sprint 2 videos | TEAM ACTION | No tracked outcome videos were found; supply the actual files/links |
| Final report, maintenance, risks and retrospectives | PASS as review artifacts | TSMP-23/24 documents, PDFs, deck and captioned evidence; team review of reconstructed retrospectives remains necessary |
| Five first-time usability participants (USA-01) | TEAM ACTION | Protocol/templates exist; automated browser checks do not supply participant observations |
| Complete SRS portability evidence | PARTIAL | Current macOS stack/Chrome browser and historical Linux CI; Firefox could not launch its local profile; Windows Docker and current Firefox/Edge evidence remain required |
| Final operating-window availability | PASS in defined local window | 30/30 samples up over five minutes; earlier failed resource-contention window retained |
| Final 50-user performance run | PASS | 7,575 requests; zero failures; aggregate p95 140 ms; highest route p95 180 ms |
| Final demo and viva | TEAM ACTION | Rehearse the 15-minute deck, record the final demo and explain each member's code and design decisions |

## Implemented fixes and design updates

The React flow is complete on one browser origin, including compatibility, status, charts,
ROC class selection, guarded comparison, downloads, history filters/deletion and role
controls. Backend changes enforce evaluator read-only membership access, preserve shared
inputs, defer physical file deletion until commit, handle duplicate registration races,
verify logout-token ownership and consolidate retention. The sandbox has private mode-0700
temporary storage and verifies its effective mount/working directory. HTTPS is available
through the tested Caddy/Nginx override. ADMIN's existing hierarchy is explicitly documented
as a deviation from the original restrictive matrix.

## Evidence boundaries

The failed local availability window under SonarQube memory pressure is retained in
`evidence/final/availability-resource-contention.json`; it is not counted as a passing window.
The final isolated rehearsal window is a limited local measurement, not a long-term uptime
claim. The local Sonar run used a native ARM Java/Node runtime for the official scanner
and disabled SCM blame because this desktop checkout uses external Git object storage;
CI runs the pinned official scanner with full checkout history. The scan covers backend,
sandbox and frontend source. Server-default new-code conditions are also visible in the
raw quality-gate JSON. Lower-severity findings remain visible in SonarQube.

A release sign-off should be recorded after the team reviews the remaining participant,
platform, video and contribution evidence. No meeting, participant study, historical video,
external review or faculty acceptance is invented by this audit.

## Publication status

The final validation and preparation phase was kept local under the earlier no-push
instruction. The user subsequently authorized committing and pushing the project changes
on 9 November 2026. Captured local tests remain the evidence for the tested source; remote
CI must be assessed against its actual published commit. The private viva guide remains
outside the repository and is excluded from publication.

## Subject-project scope decision - 9 November 2026

The team stated that extra first-time participant sessions, remaining Windows/current-browser
execution and further live-board/review evidence cannot be completed for this subject delivery.
These entries remain limitations; they are not waived by faculty or relabeled as passing.
The local implementation, reports and demonstration materials are prepared. Videos are
outside this task. The private viva preparation guide is stored outside the repository.
