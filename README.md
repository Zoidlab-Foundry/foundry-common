# foundry-common

The shared platform layer for [ZoidLab Foundry](https://foundry.zoidlab.ai) apps — one
implementation of the modules every app used to carry as a pasted copy.

| Module | What it is |
|--------|------------|
| `foundry_common.auth` | Shared `zb_session` decoding + `require_pro()` gate |
| `foundry_common.entitlements` | Nyquest Pro entitlement decisions (fail-closed) |
| `foundry_common.envelope` | The signed Foundry export envelope (sha256 integrity digest) |
| `foundry_common.llm` | Nyquest relay client with per-user billing resolution |
| `foundry_common.pricing` | Model price table + measured-cost helpers |
| `foundry_common.db` | Postgres+RLS core: pool, tenant `_tx`, `apply_rls`, fork-safe Celery hook |

## Usage in an app

Each app keeps thin shims so its internal imports don't change:

```python
# backend/auth.py
from foundry_common.auth import *  # noqa: F401,F403
```

Apps with genuinely app-specific behavior keep that behavior in their shim, on top of
the shared base.

## Install

```
pip install "foundry-common @ git+https://github.com/Zoidlab-Foundry/foundry-common@v0.1.0"
```

Pin a tag. A security fix lands here once, then each app bumps the pin and redeploys
(`foundry-deploy.sh <app>`).

## License

MIT — part of the ZoidLab Foundry platform.
