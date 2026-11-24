# Group C — Script-first Microsoft Store rollout and teacher-data plan

Date: 2026-11-20 JST

## Goal

Use the successfully proven Folder Automation Engine Store lane as teacher zero, then
process Group C one product at a time. Each successful product must add reusable
fixtures/receipts/selectors so later products require less manual browser work.

The default operating model is:

1. lightweight Windows smoke QA;
2. freeze exact source/package identity;
3. script-driven Partner Center draft completion and package upload;
4. Save + reload reconciliation;
5. record teacher data;
6. stop before Certification/Publish unless separately authorized.

Do not repeat heavyweight manual QA when CI + prior real-device evidence already
cover the same behavior. Human work should be limited to genuinely visual, legal,
identity, pricing, or unknown-Microsoft-state decisions.

## Order

Process in this exact order unless a product is blocked:

1. Data Contract Auditor
2. Web Evidence Archiver
3. Excel / CSV Privacy Cleaner
4. Image Privacy Cleaner
5. AI Upload Guard
6. PDF Privacy

If one product encounters a true blocker, hold that product and continue to the next
only when doing so cannot contaminate teacher data or shared route state.

## Teacher zero

Folder Automation Engine is the current teacher product for:

- recovered existing Draft binding;
- exact local MSIX pre-upload gate;
- single-attempt package upload;
- upload -> analyzing -> validated reconciliation;
- known runFullTrust warning handling;
- Packages Save -> Overview -> reload persistence;
- Store Draft lifecycle state separation;
- Known User Group / Private Audience handling;
- fail-closed behavior on unknown state;
- no Certification/Publish side effects.

Do not generalize Folder-specific Store ID, package SHA, price, text, security
answers or assets into Group C defaults.

## Group C source state

All six products are currently:

`READY_FOR_WINDOWS_REAL_DEVICE_QA`

GitHub-generated packages are `QA_UNSIGNED` validation packages. Their
workflow-generated versions and placeholder assets are not formal Store values.

Never weaken Windows security policy or add unknown certificates just to install a
QA_UNSIGNED package.

## Lightweight real-device QA policy

For each Group C product, perform a short but meaningful smoke test on Windows 11
before formal Store candidate creation.

Required minimum:

- launch portable EXE from the exact source checkpoint;
- 100% DPI primary run;
- one additional DPI spot-check at 125% or 150%;
- JA / EN spot-check where both exist;
- one normal input;
- one invalid/error input;
- one successful output;
- prove original input remains unchanged when the product claims non-destructive
  behavior;
- close and relaunch once;
- confirm no clipping / missing primary button / startup crash.

Do not require a full exhaustive matrix again if:
- GitHub regression/packaged EXE smoke is already green;
- the product behavior is unchanged;
- no visual/runtime defect appears in the smoke.

If a defect is found, expand QA only around the failing area.

## Product smoke cases

### 1. Data Contract Auditor
- valid CSV comparison with schema/data-quality differences;
- malformed/unreadable input;
- source files unchanged;
- result/severity filtering understandable.

### 2. Web Evidence Archiver
- one simple HTTPS page;
- one invalid/unreachable URL;
- expected evidence output exists;
- partial failure is not reported as complete success.

### 3. Excel / CSV Privacy Cleaner
- one CSV privacy transform;
- one XLSX spot-check if supported;
- preview matches export;
- original unchanged.

### 4. Image Privacy Cleaner
- one image metadata-removal case;
- one visible redaction case;
- one corrupt/unsupported image;
- original unchanged.

### 5. AI Upload Guard
- one safe file;
- one clear BLOCK;
- one ambiguous/REVIEW case;
- reason text understandable.

### 6. PDF Privacy
- one metadata/privacy operation;
- one supported page/document operation;
- one malformed/encrypted/unsupported error path;
- original unchanged.

## QA_UNSIGNED install policy

If unsigned MSIX installation is blocked by Windows security/signing policy:

record:

`HOLD_UNSIGNED_PACKAGE_POLICY_BLOCK`

Do not:
- disable Application Control;
- alter enterprise security policy;
- install an unknown test certificate;
- treat the policy block as a product defect by itself.

Continue functional/UI QA using the exact-source portable EXE where permitted.

## Formal Store candidate gate

After lightweight real-device QA passes:

`WINDOWS_REAL_DEVICE_QA_PASS`

Then require explicit formal values before Store MSIX creation:

- formal Store Version;
- final icon/logo/brand assets;
- final manifest languages/resources;
- exact Store Identity / Publisher;
- same approved source HEAD.

QA workflow-generated Version must never be promoted automatically.

Placeholder logos must never be promoted automatically.

If any formal value is unknown:

`HOLD_FORMAL_STORE_VALUE_REQUIRED`

## Formal candidate generation

Build a new formal Store candidate from the approved source HEAD.

Record:

- source SHA;
- formal Version;
- Identity;
- Publisher;
- architecture;
- EXE SHA-256;
- MSIX SHA-256;
- workflow run;
- artifact ID;
- manifest;
- package languages;
- final asset hashes.

Unpack the formal MSIX and verify all of the above again.

Only then:

`READY_FOR_PARTNER_CENTER_PACKAGE_UPLOAD`

## Script-first Partner Center rule

After Folder teacher-zero completion is proven, Group C Store browser work should be
script-first.

Human browser actions should not be the default.

The script should perform, where the live route has verified selectors:

- exact product / Store ID / Draft verification;
- existing Draft recovery or initial-Draft reconciliation;
- package upload;
- upload-state reconciliation;
- package validation classification;
- Packages Save;
- reload verification;
- Pricing and availability using owner-approved fixed values;
- Properties using package/source evidence;
- Store listings using exact product fixtures/assets;
- Submission Options using package-bound capability evidence;
- Overview reconciliation.

IARC may be scripted up to the legal-attestation boundary.

## Manual boundaries

Stop for human input only when required:

- Store ID / Identity / Publisher / Version mismatch;
- unknown Microsoft warning/error;
- unknown or changed Partner Center selector/state;
- owner price/market decision not previously fixed;
- final visual asset approval;
- privacy/legal declaration not supported by implementation evidence;
- IARC personal/legal attestation;
- Certification;
- Publish;
- new Store product creation.

Known safe Save/reload/package operations should not repeatedly request approval.

## Certification / Publish

This rollout does not authorize either action.

After a product reaches:

`STORE_DRAFT_COMPLETE`

transition only to:

`READY_FOR_CERTIFICATION_REVIEW`

Do not click Submit for certification.

Do not click Publish.

## Teacher-data requirement for every successful product

Every completed product must add:

1. exact product fixture;
2. Partner Center observation fixture;
3. package upload receipt;
4. section Save/reload receipt;
5. selector/label mapping only for observed live UI;
6. screenshot upload reconciliation evidence;
7. known warning/error classification;
8. final Overview 6/6 section receipt;
9. regression tests proving the next product cannot bypass the same gate.

Each teacher entry must include exact source/package provenance.

## Learning progression

### Product 1 — Data Contract Auditor
Operate conservatively.
Capture detailed live labels/selectors and receipts.

### Product 2 — Web Evidence Archiver
Reuse Product 1 route logic.
Only add deltas.

### Product 3 — Excel / CSV Privacy Cleaner
Expect most app-route logic to be scripted.
Manual intervention should be limited to real product-specific decisions.

### Products 4–6
Default to script-only Store execution after the lightweight Windows smoke and exact
candidate binding, unless a new Partner Center UI/state appears.

## Do not overfit

Never copy:
- product-specific security answers;
- listing text;
- pricing;
- screenshots;
- package language assumptions;
- capability justifications

from one product to another.

Generalize only route mechanics.

## Final per-product states

Allowed progression:

`READY_FOR_WINDOWS_REAL_DEVICE_QA`
-> `WINDOWS_REAL_DEVICE_QA_PASS`
-> `READY_FOR_FORMAL_STORE_MSIX`
-> `FORMAL_STORE_MSIX_FROZEN`
-> `READY_FOR_PARTNER_CENTER_PACKAGE_UPLOAD`
-> `PACKAGE_SAVED`
-> `STORE_DRAFT_REMAINING_SECTIONS_REQUIRED`
-> `STORE_DRAFT_COMPLETE`
-> `READY_FOR_CERTIFICATION_REVIEW`

Certification and Publish are separate future gates.
