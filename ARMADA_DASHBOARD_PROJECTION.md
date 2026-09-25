# Armada private dashboard connection

Uses the existing Hermes API listener and its existing bearer authentication.
The native dashboard remains bound to `127.0.0.1:9119` under the image's s6 supervisor.
No additional Railway service, public port, tunnel, account or API key is created.

Required environment:
- `HERMES_DASHBOARD=true`
- `HERMES_DASHBOARD_HOST=127.0.0.1`
- `HERMES_DASHBOARD_SESSION_TOKEN=${{ API_SERVER_KEY }}` (Railway same-service reference)

Exposed authenticated projections:
- `GET /armada-dashboard/api/status`: actual dashboard version and explicit read-only mode.
- `GET /armada-dashboard/api/skills`: names, enabled state and provenance only.

All other paths are rejected. All mutations are rejected. Query/profile switching is rejected.
The response never forwards configuration values, credentials, session contents, skill contents,
filesystem paths, MCP environment variables, or dashboard HTML/session-token injection.
The public workspace currently has no authenticated owner session; enabling arbitrary admin APIs
through its server-side bearer would expose management to every visitor. This bridge does not do so.
The read projection is not full dashboard management and is not ULTRACOMM execution authority.

Qualification uses the exact currently deployed base-image digest, with no network and synthetic
credentials. Tests cover real HTTP auth, status/skills readback, redaction, missing auth, blocked
mutations/config/profile requests, malformed responses and response-size limits.
Existing model/provider configuration, public gateway listener, Orgo voice and ULTRACOMM are unchanged.
