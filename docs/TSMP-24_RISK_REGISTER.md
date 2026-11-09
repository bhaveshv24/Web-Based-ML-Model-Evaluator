# Team 13 risk register
Prepared by Bhavesh Velluru. Review date 9 November 2026. Baseline `3f11b12`.

Likelihood and impact use Low, Medium and High. Ratings are qualitative assessments for team review. Owners follow functional responsibility. Next review is the final submission review, and thereafter each release or material incident.

| ID | Risk | Likelihood | Impact | Owner | Current control / evidence | Remaining action / trigger |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Uploaded pickle/joblib executes hostile code | Medium | High | Ayush | Per-job hardened Docker, containment tests and no labels in sandbox | Suspend execution on policy failure; rerun hostile suite after runtime/image changes |
| R-02 | Unauthorized access to another user's data | Medium | High | Atharva Anand | Ownership checks, JWT/IDOR tests and security matrix | Resolve evaluator/ADMIN policy (DEF-05/06), then retest matrix |
| R-03 | Memory/process exhaustion or abandoned jobs affect host | Medium | High | Ayush | Resource caps, timeout, reaper and CI recovery checks | Monitor queue age and orphan containers; investigate cleanup failures |
| R-04 | Model/runtime version mismatch gives invalid inference | Medium | Medium | Atharva Rakesh + Ayush | Pinned sandbox dependencies and compatibility inspection | Rebuild fixtures after version changes; expose sanitized failure |
| R-05 | Dated validation documents misstate the merged UI | High | High | Bhavesh + Ayush | Final report records baseline and dates; Part 3 reconciliation planned | Rerun original UI cases and update RTM before claiming release acceptance |
| R-06 | Five-user usability study or second-host evidence is unavailable | High | Medium | Atharva Rakesh + Bhavesh | Protocol and portability script exist | Obtain real participants/host; keep blocked outcomes visible until executed |
| R-07 | HTTPS or SonarQube requirement remains unmet | High | Medium | Team; M1/M3 coordinate | DEF-09/10, CI scans and coverage | Configure required deployment/gate or record reviewed deviation |
| R-08 | Secrets scanner flags fixtures or actual credentials | Medium | High | All | Runtime-generated test credentials, env-only deployment secrets, CI scan | Review finding context; rotate any real credential and record resolution |
| R-09 | Integration changes break shared APIs, retention or deployment | Medium | High | All module owners | PR reviews, regression tests, Compose smoke and migration checks | Reconcile parallel implementations; rerun affected checks before merge |
| R-10 | Late delivery leaves insufficient retest time | High | High | Bhavesh + team | Final commit handoff and explicit remaining-work list | Freeze scope, preserve actual dates and coordinate submission with faculty |
| R-11 | Data loss during purge, deletion or migration | Medium | High | M1 + M2 + M3 | Active-input retention guards and deletion tests | Decide shared-upload lifetime; test backup restoration before operational use |
| R-12 | Demo depends on unavailable services or stale fixtures | Medium | Medium | Bhavesh | Demo runbook, existing captures and reproducible CI | Rehearse from a clean stack; keep an honest dated recording as fallback |

## Review and escalation
The affected owner updates the risk after a defect, failed check, dependency change or scope change. High-impact security/containment risks require team review before untrusted execution resumes. Record accepted deviations with reviewer, date, scope and expiry when a decision is actually made. No risk acceptance is implied by this register.
