# Web Based ML Model Evaluator
## Team 13 final report
PES University, Bengaluru | UE24CS341A Software Engineering | Semester V

Prepared by Bhavesh Velluru on 9 November 2026. Review version 1.1. Final implementation and evidence are identified by `docs/evidence/final/source-manifest.json`. This report consolidates the submitted baseline and the implementation available at that commit. Release acceptance remains conditional on the outstanding validation below. A separate project ID was absent from the supplied cover sheet; Team 13 is used as the submission identifier.

## 1. Synopsis and ownership
Students, researchers and teaching assistants repeatedly write scripts to load trained models, validate CSV inputs, compute metrics and compare runs. This application supplies a common workflow with isolated inference, trusted scoring and exportable results. The stakeholders are ML engineering students, researchers and course evaluators.

| Member | USN / SRN | Functional ownership |
| --- | --- | --- |
| Atharva Anand | PES1UG24CS092 / PES1202401515 | M1 authentication, roles, history and workspaces |
| Atharva Rakesh Bidre | PES1UG24CS095 / PES1202400624 | M2 model/CSV ingestion, target selection and compatibility |
| Ayush M Shetty | PES1UG24CS103 / PES1202403695 | M3 Celery lifecycle, sandbox and trusted metrics |
| Bhavesh Velluru | PES1UG24CS115 / PES1202400414 | M4 dashboards, comparison and JSON/PDF export; final documentation |

The scope supports already-trained scikit-learn pickle/joblib and ONNX models, tabular classification and regression, and CSV test data. Training, GPU inference, deep-learning frameworks and image/video/NLP pipelines are outside Version 1 scope. The approved proposal is [Team13_Synopsis.pdf](../Team13_Synopsis.pdf).

## 2. Requirements and validation baseline
The approved combined [SRS/SAD/STP](../Team13_SRS_SAD_STP.pdf) identifies 27 functional, 10 security and 11 non-functional requirements. Its requirement IDs are the primary references for this report. The shorter [SRS](../Team13_SRS.pdf) is retained as earlier context.

| Requirement group | Delivered behavior | Evidence entry point |
| --- | --- | --- |
| FR-001..007 | Registration, JWT rotation/logout, role checks, private history, workspaces | tests/test_auth_history_workspaces.py |
| FR-008..013 | Upload checks, CSV limits, target selection, sandbox compatibility inspection | tests/test_ingestion.py; tests/test_ingestion_api.py |
| FR-014..021 | Asynchronous lifecycle, task detection, trusted metrics, timeout, cleanup | tests/test_evaluation_jobs.py; tests/test_metric_engine.py |
| FR-022..027 | Charts, guarded comparison, best values, JSON and PDF exports | tests/test_benchmarking.py |
| SEC-001..010 | Authentication, object access, file validation, containment, audit and configuration checks | tests/test_tsmp21_security.py; tests/test_sandbox_docker.py; tests/test_tsmp21_sec009.py |
| NFR-001..011 | Timing, concurrency, recovery, portability, retention and quality checks | scripts/performance/; tests/test_retention.py; docs/TSMP_19_20_VALIDATION.md |

The complete chain is in [the RTM](TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md). That matrix and the 6 November validation reports predate the React merge. Their missing-UI findings need a final retest and reconciliation during Part 3. A source file's presence alone does not verify a requirement.

## 3. Project plan and Agile delivery
The approved baseline described six two-week iterations. The delivery backlog grouped work into three delivery sprints. The course Part 2 dates were 19-23 October and 26-30 October, with optional spillover/testing on 2-6 November. Git history shows Sprint 2 and Sprint 3 merges continuing in November. The team should present the actual history and carry-over dates in the demo.

| Delivery group | Stories | Available outcome |
| --- | --- | --- |
| Sprint 1 | MLE-01..08 | Repository/CI, auth/history/workspaces and input validation |
| Sprint 2 | MLE-09..16 | Worker/sandbox, metrics, dashboards, comparison and reports; PRs #29 and #30 |
| Sprint 3 | MLE-17..22 | React workflow, security matrix, performance/retention tools and validation records; PRs #31, #32 and #33 |
| Final submission | MLE-23..24 and Part 3 | Consolidated report, maintenance, demo, risks, retrospectives and final test reports |

The module owners implement features, open linked PRs and review one another's changes. Pull requests and commits supply contribution evidence. Historical dates and individual authors should be read directly from GitHub, since author identity in a commit alone cannot prove who performed a review.

## 4. Architecture and design
React/Vite serves the user workflow through an Nginx frontend. Django REST Framework exposes versioned APIs. PostgreSQL stores users, workspaces, uploaded-file metadata, compatibility reports, evaluations and report references. Celery workers consume Redis jobs. A restricted Docker socket proxy permits creation of a hardened container per evaluation. ReportLab renders downloadable PDFs.

Inference receives only staged model and feature inputs. Ground-truth labels and trusted metric computation stay outside the sandbox. Each job has enforced CPU, memory, process, filesystem and network constraints, with a 120-second runtime limit and cleanup/reaping paths. The approved SAD contains component, deployment, class, sequence, activity and ER diagrams; [M3 traceability](M3_TRACEABILITY.md) connects execution design to code.

The principal API groups are `/api/v1/auth`, `/models`, `/datasets`, `/compatibility-reports`, `/evaluations`, `/comparisons` and `/workspaces`. Uploads are validated before queuing. A successful compatibility result is required to create an evaluation. The queue returns 202 and a status URL; completed results provide metrics/charts and report downloads. Error responses use sanitized codes and preserve ownership checks.

## 5. Implementation and product workflow
The React routes in `frontend/src/App.tsx` include registration, login, upload, evaluation results, history and workspace. React now provides classification/regression charts, compatible comparison, downloads, history filters/deletion and role-specific controls in the same session. The earlier Django `/results` dashboard remains available.

1. Register or sign in, then upload a supported trained model and CSV.
2. Choose the target and inspect compatibility results. Invalid or mismatched inputs receive an explanation.
3. Submit a compatible pair, poll the queued/running status and open the completed evaluation.
4. Inspect classification metrics, confusion matrix and ROC curves, or regression errors and residual plots.
5. Compare 2-5 successful owned runs with the same dataset checksum and task. Export JSON/PDF and inspect history/workspaces as the role permits.

Comparison minimizes MAE/MSE/RMSE and maximizes other scored scalar metrics. Exact ties select the first submitted evaluation. Upload paths use UUIDs; stored checksums preserve provenance. History survives expiry of uploaded files.

## 6. Testing and current evidence
| Evidence scope | Recorded outcome | Qualification |
| --- | --- | --- |
| Sprint 2 | 273 tests passed; 96.17% backend coverage | Historical run in SPRINT_2_EVIDENCE.md |
| 6 November validation | 381 passed; 7 strict xfails; 97.34% coverage | Historical execution report; contains missing-UI findings |
| 9 November final regression | 416 passed; zero failures, skips or expected failures; 97.36% backend line coverage | Local Python 3.11 with Redis and real Docker; raw JUnit in docs/evidence/final |
| Updated CI | Core, security, sandbox, Compose and cross-OS tooling checks | All captured checks succeeded, including the deployed performance workflow; see evidence index for exact runs |
| Branch coverage | 92.67% (493/532 destinations) | Same final branch-enabled full-suite run |

The former expected failures are resolved through evaluator access fixes, HTTPS configuration and the documented ADMIN hierarchy. Final regression has no expected failures or infrastructure skips. The merged React workflow passed its final 11-scenario browser run. The five-participant usability study still needs real participants. Windows tooling checks exercise scripts, while full portability needs the actual Compose deployment on the required hosts.

The Part 3 package now contains updated cases and the four reports in `docs/`. See UNIT_TEST_REPORT.md, SYSTEM_VALIDATION_REPORT.md, CODE_COVERAGE_REPORT.md and BRANCH_COVERAGE_REPORT.md. Use one final commit, expected/actual outcomes and reproducible evidence links. See [test execution report](TSMP-21_TEST_EXECUTION_REPORT.md) and [defect register](TSMP-21_DEFECT_REGISTER.md).

## 7. Validation, limitations and open decisions
The 6 November report counted 41 verified, 5 partial, 1 unverified and 1 unimplemented requirement. This is a dated baseline, not the acceptance count for the merged build. The new frontend and final browser run resolve the four earlier UI case failures. The human usability case remains separate and blocked pending participants.

Evaluator access, React controls, shared-upload deletion and HTTPS configuration have been implemented and tested. The retained ADMIN hierarchy is explained in FINAL_SRS_SAD_STP_UPDATE.md. Final measured SonarQube, performance, availability and outstanding environment/human evidence are recorded in FINAL_SUBMISSION_CHECKLIST.md. Acceptance of deviations must be recorded by the team/course reviewer.

The project is ready for final validation and demonstration preparation. Release acceptance requires the STP conditions to be evaluated on the final build, including High-priority requirements, the overall pass rate, open High/Critical defects and quality/security gates.

## 8. Screenshots and demo evidence
The captioned [demo evidence index](TSMP-23_DEMO_EVIDENCE.md) links seven existing product captures, PRs, source documents and CI runs. Those captures show the earlier `/results` dashboard. They are dated evidence of that surface. New React workflow captures are in docs/evidence/final/browser; the final narrated recording remains a team action.

## 9. Maintenance
The [maintenance plan](TSMP-23_MAINTENANCE_PLAN.md) defines corrective, adaptive, perfective and preventive work, owner responsibilities, regression checks, backup/recovery, retention and rollback.

## 10. Outcomes and further work
The project supplies reusable evaluation and comparison for uploaded trained tabular models, with isolated inference and scoring outside the untrusted process. The team produced a requirements/design/test baseline, incremental implementation, PRs and automated evidence. Further work includes closing the recorded policy/deployment gaps, measuring usability and availability, maintaining dependency pins and reconciling the final validation record.

## Appendices
- [Repository](https://github.com/bhaveshv24/Web-Based-ML-Model-Evaluator)
- [GitHub issues](https://github.com/bhaveshv24/Web-Based-ML-Model-Evaluator/issues)
- [Backlog and ownership](JIRA_BACKLOG.md)
- [CI and demo evidence](TSMP-23_DEMO_EVIDENCE.md)
- [Risk register](TSMP-24_RISK_REGISTER.md) and [retrospectives](TSMP-24_SPRINT_RETROSPECTIVES.md)

The PDF edition appends the approved Synopsis and SRS/SAD/STP unchanged, followed by captioned historical dashboard captures. Those baseline pages retain their original dates and numbering. The dated implementation and validation qualifications in this report govern the current release assessment.
