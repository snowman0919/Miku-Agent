# Authentication and Access Control

## Dual gate

Clerk는 identity, sign-in, session, token issuance와 exact-email Allowlist 기반 signup gate를 제공한다. Backend access grant는 application access, role, suspension, revocation, resource ownership의 runtime gate다. Access mode는 Open, Allowlist는 enabled를 목표로 하며 domain wildcard는 기본 사용하지 않는다.

모든 backend request는 (1) Clerk token의 signature·issuer·audience·expiry 검증, (2) `provider=clerk`와 `provider_subject`를 application UUID인 `internal_user_id`에 mapping, (3) `access_grant.status=active`, (4) resource owner 일치를 모두 만족해야 한다. 기본 정책은 deny다. 이메일은 primary key가 아니다.

## Account state and role

상태는 `pending`, `active`, `suspended`, `revoked`, role은 `owner`, `tester`로 제한한다. 기존 사용자를 Clerk Allowlist에서 제거하는 것만으로 충분하지 않다. Backend grant를 revoke하고 cache/session에 전파하여 즉시 차단한다.

장시간 WebSocket은 handshake 때 token과 grant를 검사하고, 주기적으로 또한 tool·memory write·scheduler·Codex 같은 중요 action 직전에 authorization을 재검사한다. revoke event는 active connection을 종료하거나 제한 상태로 바꾼다. replay 방지를 위해 token expiry, nonce/session binding과 TLS를 사용한다.

## Secret and metadata boundary

Clerk secret은 client나 model prompt에 저장하지 않는다. client는 public configuration과 short-lived token만 사용한다. Clerk metadata에는 장기·project·character memory를 저장하지 않는다.

Flutter는 auth adapter 뒤에서 community SDK 또는 official native Android/iOS SDK platform channel wrapper를 V0.8.1 이전에 비교한다. Clerk provider 결정은 유지한다. Production Allowlist의 plan/cost 의존성과 구체 integration 경로는 risk와 open question으로 추적한다. V0.0.0에는 production app, key, email, UI, JWT code가 없다.

