# TSMP-18 authorization and input-security matrix

Scope: SEC-001..004 and SEC-007..010. This matrix maps role decisions and untrusted inputs to the
API controls and automated test evidence. Docker-only model containment is tracked separately and
must be verified by the `sandbox-tests` CI job.

## Role × action

`401` is an absent/invalid token. `403` is an authenticated caller without the required role.
`404` is used for unknown or foreign-owned objects to avoid disclosing their existence.

| Action | Anonymous | USER | EVALUATOR | ADMIN | Control and evidence |
|---|---|---|---|---|---|
| Register / login | Allow | Allow | Allow | Allow | Explicit public auth views; password validation; generic failed-login message. `test_registration_rejects_weak_password_and_hashes_strong_password`, `test_wrong_password_is_generic_and_audited`. |
| Upload / read own model and dataset | 401 | Own only | Own only | Own only | JWT + `IsAuthenticated`; owner assigned from `request.user`. `test_model_upload_requires_authentication_and_file`, `test_model_is_private_to_owner`, `test_dataset_is_private_to_owner`. |
| Change target / create and read compatibility report | 401 | Own artifacts | Own artifacts | Own artifacts | Revalidate target against parsed CSV; object queries include owner. `test_target_can_be_overridden_after_upload_and_is_revalidated`, `test_report_inputs_are_validated_and_owner_scoped`. |
| List/read/delete evaluation, charts, export | 401 | Own only | Own only | Own only | Owner-scoped queryset on each detail endpoint. `test_history_is_owned_newest_first_and_filterable`, `test_non_owner_receives_404_for_detail_and_delete`, report ownership cases in `test_benchmarking.py`. |
| Create workspace / add members / view workspace evaluations | 401 | **403** | Own workspace | Own workspace | `IsEvaluator` and evaluator-owner filtering. `test_user_cannot_manage_workspaces_and_denial_is_audited`, `test_evaluator_can_create_workspace_add_member_and_view_only_its_evaluations`, `test_evaluator_cannot_manage_another_evaluators_workspace`. |

## Input × risk × control × evidence

| Input | Risk | Control | Expected outcome / test |
|---|---|---|---|
| JWT access/refresh | Forged, stale or replayed token | SimpleJWT validation; 15-minute access; rotating 7-day refresh; blacklist on rotation/logout | 401 on invalid credentials; `test_login_issues_role_token_with_required_lifetimes`, `test_refresh_rotates_and_blacklists_old_token`, `test_logout_revokes_refresh_token`. |
| Login attempts | Credential guessing | Five attempts per minute per IP/email; failed-login audit | 429; `test_login_is_limited_to_five_attempts_per_ip_and_email`. |
| Model suffix, signature, size, filename | Disguised executable; traversal; disk exhaustion | `.pkl`/`.joblib`/`.onnx` allow-list, content-signature checks, 100 MB limit, server UUID storage path | 400 invalid / 413 oversized; `test_disguised_content_is_rejected`, `test_oversize_model_returns_413`, `test_valid_model_is_stored_under_uuid_name_with_sha256` submits `../../evil name.PKL` and asserts UUID storage. |
| Pickle/joblib bytes | Code execution during deserialization | Web process never unpickles; inspection/execution only in isolated worker sandbox; fail closed when inspector unavailable | `test_report_fails_closed_when_no_safe_inspector_exists`; hostile container tests in `test_sandbox_docker.py` need Docker. |
| CSV bytes/header/rows | Parser exhaustion, malformed data, missing features | UTF-8 validation; 50 MB, 500k row, 1,000 column and 255-char header limits; bounded errors | 400 invalid / 413 oversized; `test_invalid_csv_is_rejected_with_issue_code`, `test_oversize_dataset_returns_413`, `test_very_wide_csv_is_rejected_quickly`, `test_row_level_errors_are_capped`. |
| Target column | SQL-like value or nonexistent field | Must be a string in parsed CSV header; file is revalidated before update | 400; target stays unchanged; `test_unknown_target_override_is_rejected`, `test_non_string_target_column_is_a_400`, `test_sql_payload_target_is_rejected_without_changing_dataset`. |
| JSON IDs / filters | SQL injection, malformed UUID, IDOR | DRF validation and parameterized Django ORM; owner-scoped lookup | 400 schema / 404 foreign or unknown ID; `test_model_id_sql_payload_is_not_interpreted_as_a_query`, `test_report_inputs_are_validated_and_owner_scoped`, `test_non_owner_receives_404_for_detail_and_delete`. |
| Original filenames and API text in UI | Path traversal / stored HTML injection | UUID file paths; React renders text values (no `dangerouslySetInnerHTML`) | Traversal assertion in `test_valid_model_is_stored_under_uuid_name_with_sha256`; React escapes text by default. |
| Evaluation task type / metrics | Unsupported task or client-controlled scoring | Serializer allow-list; target-driven task detection; metrics fixed server-side; predictions validated | `test_evaluation_inputs.py`, `test_metric_engine.py`, `test_evaluation_jobs.py`. |

## Execution record

Run from the repository root:

```powershell
python -m pytest tests/test_auth_history_workspaces.py tests/test_ingestion_api.py tests/test_benchmarking.py -q
```

Local execution on 2026-11-06: **89 passed**, with one ReportLab `ast.NameConstant` deprecation
warning. Record the CI URL and result in Jira. A local run without Docker does not count as passing
the hostile-container suite; CI uses `REQUIRE_DOCKER_TESTS=1` so missing Docker fails the job.

The React client keeps the access token in memory and the rotating refresh token in tab-scoped
`sessionStorage`; it sends bearer-authenticated requests through the same-origin API proxy and
renders untrusted strings as React text. Vite dev/preview also set a restrictive CSP, `nosniff`,
same-origin referrer policy and frame denial. Server-side role and ownership checks remain
authoritative.
