# AEON Python SDK

Official Python client for the [AEON OS](https://github.com/beatznlg/aeon) API.

## Installation

```bash
cd sdk/python
pip install -e .
```

## Quick Start

```python
from aeon_sdk import AeonClient

client = AeonClient("https://your-aeon-backend.up.railway.app", api_key="aeon_...")
print(client.health())
print(client.chat("What is the integral of x^2?"))
```

## Authentication

- **API key**: pass `api_key` or set `AEON_API_KEY`
- **JWT token**: pass `token` or log in with `client.login(email, password)`

## Environment Variables

| Variable | Description |
|---|---|
| `AEON_PYTHON_URL` | Default backend URL |
| `AEON_API_KEY` | Default API key |

## API Coverage

See the TypeScript SDK or `docs/openapi.json` for the full API surface.

## License

MIT
