# Team 13 risk register

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.

Prepared by Bhavesh Velluru. Review date 9 November 2026. Current implementation identified by `evidence/final/source-manifest.json`.

Likelihood and impact use Low, Medium and High. Ratings are qualitative assessments for team review. Owners follow functional responsibility. Next review is the final submission review, and thereafter each release or material incident.

| ID | Risk | Likelihood | Impact | Owner | Current control / evidence | Remaining action / trigger |
| --- | --- | --- | --- | --- | --- | --- |
| R-01 | Uploaded pickle/joblib executes hostile code | Medium | High | Ayush | Per-job hardened Docker, containment tests and no labels in sandbox | Suspend execution on policy failure; rerun hostile suite after runtime/image changes |
| R-02 | Unauthorized access to another user's data | Medium | High | Atharva Anand | Ownership checks, JWT/IDOR tests and security matrix | Evaluator read/membership revocation tested; explain retained ADMIN hierarchy and obtain actual review |
| R-03 | Memory/process exhaustion or abandoned jobs affect host | Medium | High | Ayush | Resource caps, timeout, reaper and CI recovery checks | Monitor queue age and orphan containers; investigate cleanup failures |
| R-04 | Model/runtime version mismatch gives invalid inference | Medium | Medium | Atharva Rakesh + Ayush | Pinned sandbox dependencies and compatibility inspection | Rebuild fixtures after version changes; expose sanitized failure |
| R-05 | Dated validation documents misstate the merged UI | High | High | Bhavesh + Ayush | Final report/RTM reconciled against final execution evidence | Keep participant and environment gaps visible; refresh reports after any code change |
| R-06 | Five-user usability study or second-host evidence is unavailable | High | Medium | Ayush (study) + Anand (platform); Bidre supports UI | Protocol and portability script exist | Obtain real participants/host; keep blocked outcomes visible until executed |
| R-07 | HTTPS or SonarQube requirement remains unmet | High | Medium | Atharva Anand (TSMP-20), module review support | Tested HTTPS and SonarQube gate; final raw evidence | Retest after deployment/runtime changes; configure public DNS/certificate for public hosting |
| R-08 | Secrets scanner flags fixtures or actual credentials | Medium | High | All | Runtime-generated test credentials, env-only deployment secrets, CI scan | Review finding context; rotate any real credential and record resolution |
| R-09 | Integration changes break shared APIs, retention or deployment | Medium | High | All module owners | PR reviews, regression tests, Compose smoke and migration checks | Reconcile parallel implementations; rerun affected checks before merge |
| R-10 | Late delivery leaves insufficient retest time | High | High | Bhavesh + team | Final commit handoff and explicit remaining-work list | Freeze scope, preserve actual dates and coordinate submission with faculty |
| R-11 | Data loss during purge, deletion or migration | Medium | High | M1 + M2 + M3 | Active-input retention guards and deletion tests | Last-reference deletion/rollback verified; rehearse backup restoration before operational use |
| R-12 | Demo depends on unavailable services or stale fixtures | Medium | Medium | Bhavesh | Demo runbook, existing captures and reproducible CI | Rehearse from a clean stack; keep an honest dated recording as fallback |

## Review and escalation
The affected owner updates the risk after a defect, failed check, dependency change or scope change. High-impact security/containment risks require team review before untrusted execution resumes. Record accepted deviations with reviewer, date, scope and expiry when a decision is actually made. No risk acceptance is implied by this register.
