# Device registration prototype

This is an isolated staging prototype, not a production backend. It has an
administrator-only registration and deletion endpoints and encrypts device
tokens before storing them in D1. It can send a single Huawei test notification
only when explicitly enabled and supplied with a short-lived service JWT.
Acceptance by Huawei is not a delivery receipt. No administrator credential
belongs in the App or GitHub. It has no end-user registration or deletion,
delivery tracking, rate limiting, scheduled scanning, key rotation, or
deployment configuration. Do not deploy it for public users.

Before production, implement authenticated user/device registration, consent,
revocation and deletion, abuse protection, secret rotation, secure delivery,
monitoring, privacy documentation, and real-device integration testing.
