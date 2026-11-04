# M3 traceability - MLE-9 to MLE-12

Requirement -> design -> code -> tests for the Sandboxed Model Execution and Metrics Engine (owner: Ayush M Shetty). STP IDs refer to Part C of `Team13_SRS_SAD_STP.pdf`.

| Req | Jira | Design | Code | Automated tests (STP ID) |
|---|---|---|---|---|
| FR-014 | MLE-9 | API-15, Fig. 7, D-01 | `evaluations/views.py`, `services.py`, `tasks.py` | `test_post_returns_202_queued_immediately_and_enqueues_once` (IT-EXE-01), `test_async_e2e.py` (ST-EXE-01 via real Redis/Celery) |
| BR-01 | MLE-9 | Fig. 7 step 2 | `services.latest_passed_report` | `test_unvalidated_failed_or_stale_pairs_cannot_be_evaluated` |
| FR-019 (states) | MLE-9 | Fig. 2, BR-04 | `services.ALLOWED_TRANSITIONS`, `transition`, `claim` | `test_ut_exe_05_illegal_transition_*` (UT-EXE-05), `test_transition_table_*`, `test_compare_and_set_*`, `test_duplicate_delivery_*` |
| FR-021 | MLE-9 | API-09/16/17, D-04 | `executor.py`, `views.py`, `Evaluation.metrics_json/charts_json` | `test_successful_evaluation_end_to_end_*` (IT-EXE-07) |
| FR-015 | MLE-10 | MetricsEngine.detectTask | `task_detection.resolve_task` | `test_ut_exe_01_*`, `test_ut_exe_02_*`, `test_ambiguous_or_unsupported_targets_*` |
| FR-017 | MLE-10 | MetricsEngine.classification, D-03 | `metrics/classification.py`, `roc.py`, `engine.py` | `test_ut_exe_03_*` (UT-EXE-03), `test_ut_exe_06_*` (UT-EXE-06), `test_classification_matches_scikit_learn_*` |
| FR-018 | MLE-10 | MetricsEngine.regression | `metrics/regression.py` | `test_ut_exe_04_*` (UT-EXE-04), `test_regression_matches_scikit_learn` |
| SAD 5.1 step 4 | MLE-10 | Trusted validation of predictions | `metrics/predictions.py`, `sandbox/base.parse_output` | `test_invalid_predictions_are_rejected`, `test_malformed_probabilities_*`, `test_parse_output_*` |
| FR-016, SEC-005 | MLE-11 | SAD 5.1 steps 1-3, D-02 | `sandbox/docker_runner.py`, `sandbox/Dockerfile` | `test_container_config_matches_the_approved_policy`, `test_policy_mismatch_fails_closed_*` (IT-EXE-04, simulated); `test_it_exe_04_daemon_applies_the_run_policy`, `test_st_sec_07_*`, `test_st_exe_02_*`, `test_st_sec_08_*` (real Docker, CI) |
| BR-06 | MLE-11 | SAD 5.1 step 1 | `inputs.split_features_and_labels`, `sandbox/workspace.py` | `test_target_is_removed_from_features_and_kept_as_labels`, end-to-end header/listing assertions, `test_st_exe_02_*` |
| SEC-004 (execution side) | MLE-11 | Path/symlink/checksum checks | `sandbox/workspace.open_trusted`, `stage_copy` | `test_staging_rejects_traversal_symlinks_and_oversize`, `test_tampered_symlinked_or_deleted_inputs_are_rejected` |
| FR-019 (timeout) | MLE-12 | SAD 5.1 step 5 | `DockerSandboxRunner._wait/destroy`, Celery time limits | `test_timeout_kills_and_removes_the_container` (IT-EXE-05, simulated), `test_it_exe_05_timeout_kills_the_model_and_all_its_children` (real Docker, CI) |
| NFR-006 | MLE-12 | Reaper | `reaper.py`, beat schedule, `worker_ready` | `test_reaper_*`, `test_worker_that_loses_ownership_*`, `test_no_job_can_stay_running_longer_than_five_minutes` (REL-01) |
| FR-020, SEC-010 | MLE-12 | Error schema | `errors.py` | `test_failures_are_categorized_sanitized_audited_and_cleaned_up` (IT-EXE-06), `test_unreachable_queue_returns_503_*` |
| SEC-006 | MLE-12 | Audit log | `audit.py` | audit assertions in `test_failures_are_categorized_*`, `test_reaper_fails_stuck_jobs_*` |

STP cases that need a real Docker host (IT-EXE-02/03/04/05, ST-EXE-02, ST-SEC-07/08) are in `tests/test_sandbox_docker.py`. They count as executed only from the CI `sandbox-tests` job; local skips are not evidence.
