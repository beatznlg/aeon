# AEON SDK Quickstarts

This directory contains minimal examples for the official AEON SDKs.

| Example | Language | File |
|---|---|---|
| Python | Python 3.10+ | `python/quickstart.py` |
| TypeScript / Node | Node 18+ | `typescript/quickstart.ts` |

## Running the Python example

```bash
# From the repo root
cd sdk/python
pip install -e .
python ../../examples/python/quickstart.py
```

## Running the TypeScript example

```bash
# From the repo root
cd sdk/typescript
npm install
npm run build
cd ../../examples/typescript
ts-node quickstart.ts
```

## Environment Variables

Both examples read the same variables:

| Variable | Description | Default |
|---|---|---|
| `AEON_PYTHON_URL` | AEON backend URL | `http://localhost:5000` |
| `AEON_API_KEY` | API key for requests | — |
| `AEON_EMAIL` | Login email | `admin@aeon.local` |
| `AEON_PASSWORD` | Login password | `admin123` |

> ⚠️ The default credentials above are for local development only.
