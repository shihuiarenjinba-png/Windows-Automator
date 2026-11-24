# Store uploader execution map

This map reproduces the successful local Playwright/CDP route. It does not make UI text evidence of a remote binary digest.

```text
ProductInput + approved existing-Draft binding
              │
              ▼
Resolve package and report paths locally
              │
              ▼
Rehash package → compare immutable SHA-256
              │
              ▼
Verify existing Store Identity (read-only)
              │
              ▼
Read Overview / Submission → exact Product ID + Draft ID
              │
              ├── mismatch / unknown / auth expired ──► HOLD; no upload
              ▼
Validate ProductInput and package identity/version
              │
              ▼
Write one-item queue; refuse empty, malformed, duplicate queue
              │
              ▼
Attach to already-authenticated local browser via CDP
              │
              ▼
Upload once → Uploading → Analyzing package
              │
              ├── timeout ──► read-only reconcile before any retry
              ├── error / unknown warning ──► HOLD
              └── known warning ──► exact product-bound policy only
              ▼
Validated + expected package row/device family
              │
              ▼
Packages Save (Draft only)
              │
              ▼
Overview → same Product/Draft → filename + Validated + Complete
              │
              ▼
Reload/reopen → package metadata retained → immutable local receipt
```

## Identity of an execution

One attempt is keyed by:

`Product ID + existing Submission/Draft ID + package filename + local SHA-256`

Partner Center's visible filename and validation state do not prove the binary SHA. A local immutable receipt proves which local bytes this runner sent, not that Microsoft independently calculated the same digest.

## Existing implementation map

| Stage | Existing component |
|---|---|
| Product state and queue | `store_manager/core.py` (`ProductInput`, `run_queue`) |
| Existing Product/Draft binding | `store_manager/live_draft.py` (`verify_product_and_draft`) |
| Verified UI route | `docs/PARTNER_CENTER_MAP.json` |
| Browser connection | `LivePlaywrightConnection` |
| Upload and Microsoft analysis | `PlaywrightPartnerCenterPort.upload_package` |
| Save/reload | `save_packages`, `reload_and_verify_package`, `verify_required_sections` |
| CLI | `python -m store_manager.cli night-run` |
| Stable Windows invocation / initialized queue path | `scripts/run_local_store_upload.ps1` |
| Route teacher from prior success | `STORE_UPLOADER_TEACHER_INDEX.json` |

The adapter in this source snapshot treats Microsoft WARNING as a hold unless product-specific code and selector-map evidence explicitly support it. Never turn a warning into VALID by relabeling.
