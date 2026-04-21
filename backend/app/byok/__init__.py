"""BYOK (Bring Your Own Key) subsystem.

This package owns everything related to user-supplied provider credentials:
crypto (envelope encryption), error normalization, per-credential
concurrency/cooldown, scope enforcement, audit logging, and the gateway that
wires it all together.

Entry points that the rest of the app should use:
    - app.byok.gateway.BYOKGateway — resolve + decrypt + dispatch a chat call
    - app.byok.crypto — envelope encrypt/decrypt primitives
    - app.byok.errors.BYOKError — normalized error surface
    - app.byok.audit.write_audit — append to credential_audit_log
"""
