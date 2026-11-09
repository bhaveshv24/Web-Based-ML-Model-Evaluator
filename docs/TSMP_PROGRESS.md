# Team 13 final status - 9 November 2026

The final automated build passes 416 backend tests without skips or expected failures,
121 dedicated unit/service cases, 15 live system cases and 11 current Chrome scenarios.
Backend line coverage is 97.36%; branch coverage is 92.67%. SonarQube passes its configured
quality gate with zero blocker/critical findings. The 50-user load run handled 7,575 requests
without errors, aggregate p95 140 ms. The defined five-minute local availability window was
100% (30/30 samples). Raw outputs are under docs/evidence/final.

The current RTM has 46 verified and 2 partial requirements. All 13 recorded defects have
current closed dispositions; historical discovery descriptions remain in the defect register.
The documented ADMIN hierarchy is an explicit design deviation.

Current reports and the remaining real-world evidence are listed in FINAL_SUBMISSION_CHECKLIST.md.
USA-01 needs five first-time participants. Full NFR-008 still needs the required Windows
Docker and current Firefox/Edge evidence. The downloaded Firefox browser failed before a
profile could open; no application test passed or failed in that attempt. Actual sprint
videos, live-board story points, individual PR/review evidence and the narrated demo/viva
must be confirmed by the team. Reconstructed retrospectives and proposed maintenance
response targets require the team's review.

Earlier TSMP-21 statistics describe 4-6 November runs and remain in Git history and the
historical execution report. The current validation report, RTM, amendment and final
reports supersede those readiness conclusions.
