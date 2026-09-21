# R62 Post-Merge Communication Handoff — 2026-09-21

Canonical main integration:
- R62 merge SHA: `3a20c14fea1644c48e5bfaf3970d6010159e93bc`;
- exact qualified PR head: `03d9b2b76356ef093f1680ee86f16286ff8dafca`;
- exact-head required CI: PASS;
- target resident server: BCP 0.7.14;
- target Telegram companion: 2026.09.21-comms-autonomy-v20.

Current field truth after merge:
- resident MBMPC is still observed on BCP 0.7.13;
- server update check is CHECK_FAILED;
- direct Telegram transport is flapping and latest readback is DEGRADED_RETRY / WinError10060;
- Nexus remains STAGE_FAILED / DNS_RESOLUTION_FAILED;
- therefore source integration is complete but resident convergence is not yet field-proven.

Do not ask the user to reinstall BCP, re-enter the Telegram token, repeatedly click the Nexus helper, or switch networks again merely for diagnosis.

Next recovery path:
1. finish/read post-merge CI;
2. observe automatic convergence to 0.7.14 + Telegram V20;
3. if raw GitHub/DNS prevents convergence, implement a Drive-local update/failover lane so communication recovery does not depend on a single Internet hostname;
4. only after the R62 runtime is field-proven may a remaining Cloudflare consent gate be exposed;
5. provider-authenticated readback remains mandatory before Nexus success.

