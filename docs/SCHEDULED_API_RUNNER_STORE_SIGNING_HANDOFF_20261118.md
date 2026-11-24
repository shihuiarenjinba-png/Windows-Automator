# Scheduled API Runner — Store-signed Private QA execution handoff

Updated: 2026-11-18 JST

## Purpose

Move the already-frozen Scheduled API Runner candidate from the technical state

`PRIVATE_STORE_SIGNING_LANE_READY`

to a Microsoft Store-signed Private test build, without changing package bytes,
bypassing Windows security, or charging the owner to acquire their own app.

This document is an execution handoff. It does **not** itself authorize Partner Center
writes.

## Immutable candidate

Product:

`Scheduled API Runner`

Store ID:

`9PND0HG61XD6`

Identity:

`OkinawaDesktopTools.ScheduledAPIRunner`

Version / architecture:

`1.0.0.0 / x64`

Frozen source SHA:

`28ef873ab2ff325b8f26c61a9ba48701280e8290`

Workflow run:

`44093493317`

GitHub artifact ID:

`14333575447`

Artifact digest:

`sha256:b45d53a0473f5b8cdcac64c1ffdcf12957919da2e5cb846564344d757165afa7`

MSIX SHA256:

`db599cdfa673688e8fe7db70d11acc69010562636c67f4996b4cba36adfd8877`

EXE SHA256:

`06d3b92bd83281750e5a454f9add6526fa90f6bfc29017fd6919bbeaa64213d9`

Do not rebuild or replace this candidate.

## Why Store-signed QA is required

The exact unsigned executable was launched once under normal-user context.

The process did not start. Windows Application Control blocked it before process
creation.

Observed evidence:

- blocking events: 3033, 3077
- supplemental event: 3118
- Activity ID: `{2f3574e4-74dd-0008-cd37-9c3add74dd01}`
- policy: `VerifiedAndReputableDesktop`
- policy GUID: `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`
- policy ID: `27555.1000.240208`
- status: `0xc0e90002`
- event flat hash equals the frozen EXE SHA256

No second unsigned launch is allowed.

Do not weaken Windows policy, add a temporary certificate, use an alternate launcher,
or install the unsigned package.

## Preconditions from Windows-all-auto

The code-owner lane reports:

- `pre_store_static_pass=true`
- `unsigned_gui_execution_status=APPLICATION_CONTROL_BLOCKED`
- `private_store_signing_lane_ready=true`
- `local_final_pass=false`
- `store_signed_install_pass=false`

These flags authorize only the next technical lane. They do not authorize Store writes.

## Microsoft Store policy facts to preserve

Private audience controls who may see/acquire the app. It does **not** automatically
make a paid app free. If the app price is paid, private-audience testers may still be
required to pay.

Promotional codes can provide free acquisition, but they are usable only after the
product has completed the Store publishing process.

Therefore never assume:

`Private audience = zero-cost acquisition`.

The zero-cost route must be proven from live Store state.

Reference:

- Microsoft Learn — MSIX visibility / Private audience
- Microsoft Learn — Generate promotional codes

## Known commercial/distribution facts from the Scheduled repository

Repository evidence already establishes:

- launch model: `FREE`
- commercial model: `free`
- strategy: `free_launch`
- currency: `JPY`
- planned free trial: `none`
- target test audience: `PRIVATE_AUDIENCE_TEST`

These are product-plan facts, not proof of the current live Partner Center values.

Therefore the preferred zero-cost path for **Scheduled** is simpler than the generic
classifier:

1. if the live Store price is already **Free**, keep it Free and use the Private
   audience Store-signed build for QA after publication;
2. if the live Store price is paid, stop at
   `HOLD_PRICE_CHANGE_APPROVAL_REQUIRED`;
3. do not invent a trial for Scheduled;
4. promo codes are not the primary path for this free-launch product;
5. never self-purchase the app.

The repository explicitly says an actual Store price/market change still requires
owner approval. A `FREE` product plan is not itself authorization to write the
Partner Center price.

Known unresolved Store-facing items:

- live price and current submission/package state;
- exact Private audience / Known User Group;
- test-account membership;
- public Privacy URL;
- Support URL;
- genuine Store screenshots.

The screenshot requirement is intentionally blocked until the Microsoft Store-signed
build can launch, because Store images must come from the genuine working app rather
than a mock or the blocked unsigned executable.

Known-facts checkpoint:

`docs/SCHEDULED_API_RUNNER_STORE_OWNER_KNOWN_FACTS_20261118.json`

## Stage 1 — read-only Partner Center observation

Before any write, inspect the live Scheduled API Runner product.

Confirm read-only:

- exact Store ID `9PND0HG61XD6`;
- current submission/Draft state;
- whether a package is already present;
- current price;
- current free-trial state;
- current audience/Private audience state;
- current Known User Group availability;
- whether the intended test Microsoft account is in the Private audience;
- whether an already-published Store-signed build exists;
- whether an existing unredeemed promo code exists;
- whether promo-code generation is available;
- whether a zero-cost free-trial acquisition is actually shown;
- whether checkout would charge money;
- whether a temporary Free change is available.

Use the checked-in observation template:

`docs/SCHEDULED_API_RUNNER_PRIVATE_ACQUISITION_OBSERVATION_TEMPLATE_20261118.json`

Do not place cookies, tokens, browser profile data, or account secrets in the receipt.

Set:

- `read_only_observation=true`
- `partner_center_write_performed=false`

## Stage 2 — classify the zero-cost route

Run:

```powershell
python scripts/classify_private_store_acquisition.py `
  --observation <private-store-acquisition-observation.json> `
  --output <new private-store-acquisition-decision.json>
```

The classifier is read-only and refuses evidence overwrite.

Possible states:

### `ZERO_COST_ROUTE_PROMO_CODE_EXISTING`

An existing unredeemed promo code is already available.

No new Partner Center write is needed to choose this route.

### `ZERO_COST_ROUTE_FREE_TRIAL`

The live Store explicitly proves the configured trial can be acquired for zero cost.

Do not infer this only from the existence of a trial setting.

### `ZERO_COST_ROUTE_PRIVATE_FREE`

The live Private build is already Free.

### `PROMO_CODE_GENERATION_REQUIRES_APPROVAL`

Promo-code generation is available but no existing code is available.

Generating a new code is a separate Store write and requires explicit approval.

### `TEMPORARY_FREE_PRIVATE_BETA_REQUIRES_APPROVAL`

A temporary Free price is technically possible, but changing price is a separate
commercial write and requires explicit approval.

This route is last resort.

### `HOLD_ZERO_COST_ACQUISITION_PAID_CHECKOUT`

The Store would charge the owner/tester.

Stop. Do not purchase the app.

### `HOLD_PRIVATE_AUDIENCE_NOT_PROVEN`

Private audience or the test account's membership is not proven.

Stop.

### `HOLD_ZERO_COST_ROUTE_UNPROVEN`

No zero-cost route has been proven.

Stop.

### `HOLD_CONFLICTING_ACQUISITION_EVIDENCE`

The observation simultaneously claims a zero-cost route and a paid checkout.

Stop and re-read the live UI.

## Stage 3 — signing/publishing writes remain separate gates

If there is not yet a Store-signed Private build, obtaining one will require Store
submission actions.

These remain separate approval gates:

1. package upload;
2. package validation/Save;
3. required Draft-section saves;
4. certification submission;
5. Private publication;
6. promo-code generation, if selected;
7. temporary Free price change, if selected.

Do not bundle these into one implied approval.

A read-only decision of

`STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED`

means only that the signed Private build does not yet exist. It does not authorize
the writes needed to create it.

## Stage 4 — exact package gate before any package upload

If package upload is separately approved later, prove immediately before the write:

- Store ID = `9PND0HG61XD6`
- Identity = `OkinawaDesktopTools.ScheduledAPIRunner`
- Version = `1.0.0.0`
- Architecture = `x64`
- frozen source =
  `28ef873ab2ff325b8f26c61a9ba48701280e8290`
- MSIX SHA256 =
  `db599cdfa673688e8fe7db70d11acc69010562636c67f4996b4cba36adfd8877`

Any mismatch:

`HOLD_EXACT_PACKAGE_MISMATCH`

Do not rebuild or substitute another artifact.

## Stage 5 — zero-cost acquisition is mandatory for owner QA

After the Store-signed Private build is actually published, re-run the read-only
acquisition observation and classifier.

Only proceed to acquisition when the decision has:

- `acquisition_allowed_now=true`
- `write_required=false`

or after the user explicitly approves the indicated write gate.

If the Store displays a paid checkout:

`HOLD_ZERO_COST_ACQUISITION_PAID_CHECKOUT`

Stop. Do not self-purchase.

## Stage 6 — signed physical QA

Only after the Store-delivered signed build is acquired should physical QA resume.

Required checks include:

1. Store delivery/install;
2. Microsoft Store signature/trust;
3. exact Store ID;
4. exact Identity;
5. exact Version;
6. JP GUI;
7. EN GUI;
8. normal exit;
9. DPI 100%;
10. DPI 125%;
11. DPI 150%;
12. owner-approved non-production HTTPS GET;
13. dated CSV append;
14. duplicate-date protection;
15. secret redaction;
16. Task Scheduler register;
17. scheduled execution;
18. expected output verification;
19. Task Scheduler unregister.

Do not invent an HTTPS endpoint.

## Stop conditions

Stop immediately on:

- Store ID mismatch;
- Identity/version mismatch;
- package SHA mismatch;
- paid checkout;
- Private audience uncertainty;
- unknown Microsoft response;
- ambiguous write result;
- authentication expiry;
- Store-signed build not actually available;
- any request to bypass security.

## Never do from this handoff without a new explicit approval

- upload the MSIX;
- Submit for certification;
- Private publish;
- Public publish;
- create/modify a Known User Group;
- generate promo codes;
- change price;
- change commercial trial settings;
- self-purchase the app.

## Completion report

Return:

### Exact candidate

- Store ID:
- source SHA:
- artifact ID:
- artifact digest:
- MSIX SHA256:
- exact match:

### Live Store observation

- submission state:
- package present:
- Private audience configured:
- test account in audience:
- Store-signed Private build published:
- current price:
- current price free:
- free trial visible:
- free trial zero-cost confirmed:
- existing promo code:
- promo generation available:
- temporary Free available:
- paid checkout required:

### Acquisition decision

- state:
- route:
- acquisition_allowed_now:
- write_required:
- owner_approval_required:

### Writes

- package upload:
- certification:
- Private publish:
- promo generation:
- price change:
- Public publish:

### Final state

Use one exact state from the classifier or a precise Store hold.

Do not claim signed physical QA PASS until the Microsoft Store-delivered signed build
has actually been acquired and tested.
