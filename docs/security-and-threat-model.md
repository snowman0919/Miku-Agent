# Security and Threat Model

| Threat | Asset | Attacker / path | Impact | Control | Residual risk | Target |
|---|---|---|---|---|---|---|
| Accidental public repository | source/contracts | operator misconfiguration | private work disclosure | create `--private`, API verify, no public fallback | provider/config error | V0.0.0 |
| Secret commit | credentials | mistake or malicious code stages secret | account compromise | ignore, tracked-file scan, broker | novel encoding | V0.0.0/V0.7.x |
| Unauthorized signup | account access | unlisted identity signs up | system entry | Clerk exact-email Allowlist | provider plan/config drift | V0.7.x |
| Existing account after removal | runtime access | formerly allowed user reuses session | continued access | backend revoke, cache invalidation, WS recheck | propagation delay | V0.7.x |
| Forged/replayed token | identity | stolen/forged JWT | impersonation | issuer/audience/signature/expiry, TLS, binding | endpoint compromise | V0.7.x |
| WebSocket hijack | live session | token theft/network attacker | audio/tool exposure | TLS, short token, heartbeat, reauth, revoke close | client compromise | V0.7.x |
| Cross-user memory exposure | private memory | missing owner filter | privacy breach | UUID ownership, namespace in every query/index | query bug | V0.7.x |
| Cross-character memory exposure | relationship memory | projection omits character | trust breach | user-and-character composite namespace | migration bug | V0.7.x |
| Prompt injection | tool authority | content instructs model | unintended action | untrusted labels, allowlist, server authorization | novel indirect injection | V0.7.x |
| Tool injection | tool arguments | model/repository crafts payload | side effect escalation | JSON Schema, permission, target validation | parser flaw | V0.7.x |
| Fake validation token | execution permission | model prints fingerprint/token | unauthorized execution | fingerprints never authorize | policy implementation bug | V0.7.x |
| Docker escape | host | malicious build/code | host compromise | no privileged/socket, isolation, patching | kernel zero-day | V0.7.x |
| Docker socket exposure | host control | mount grants daemon access | host takeover | mount prohibited and audited | operator override | V0.7.x |
| Secret exfiltration | credentials | code reads env/network | credential theft | broker/proxy, scoped TTL, egress logs | allowed destination abuse | V0.7.x |
| Malicious repository code | workspace/host | dependency/script payload | corruption/exfiltration | isolated workspace, review, watchdog | supply chain novelty | V0.7.x |
| Outbound data exfiltration | memory/source | arbitrary egress | private data loss | destination policy, DLP metadata, audit | encrypted covert channel | V0.7.x |
| Copyrighted raw data leak | media rights | accidental tracking/push | legal/data exposure | path/extension scan, external storage | disguised file | V0.0.0/V0.2.0 |
| False memory inference | user trust | weak model evidence | harmful personalization | candidate state, evidence, precision gate, user correction | subtle bias | V0.7.x |
| Memory deletion failure | privacy | stale snapshot/index/backup | retained deleted data | tombstone propagation, crypto-shredding design, compaction | backup window | V0.7.x |
| Scheduler permission escalation | external systems | edited task/replayed approval | unauthorized write | immutable permission scope, execution recheck | confused deputy | V0.7.x |
| Push data leakage | result privacy | lock-screen notification | sensitive disclosure | minimal payload, HTTPS fetch | title sensitivity | V0.7.x |

V0.0.0 controls are repository contracts and local tests이며 runtime control은 표의 target version에서 구현·검증한다.
