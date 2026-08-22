# AEON API Versioning

AEON currently keeps its established route paths for backwards compatibility and
advertises the response contract version with:

```http
X-AEON-API-Version: 1
```

## Versioned foundation

The following operational endpoints are available under `/api/v1` as well as
their legacy paths:

| Versioned path | Legacy path |
|---|---|
| `GET /api/v1/health` | `GET /health` |
| `GET /api/v1/live` | `GET /live` |
| `GET /api/v1/ready` | `GET /ready` |

The versioned probes make it possible for load balancers, deployment checks,
and clients to pin their health contract without breaking existing operators.

## Migration policy

- New public API families should be introduced under `/api/v1`.
- Existing unversioned routes remain supported until a separately announced
  deprecation window.
- When a route is promoted to `/api/v1`, its legacy path should remain an alias
  during the compatibility window.
- Both paths must preserve the same authentication, workspace authorization,
  request ID, error format, and rate-limiting behavior.
- The response header is informational; clients should use the route namespace
  as the stable version selector.

This is a compatibility foundation, not a claim that every existing endpoint
has already been migrated to `/api/v1`.
