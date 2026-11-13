# Partner Center live screen mapping — 2026-10-29

This is a read-only observation record. No file was selected, no value was
changed, and no Save, Submit for certification, or Publish action was invoked.

## Observed product and draft

- Product: `Offline Notes Canary`
- Product type: MSIX or PWA app
- Store ID: `9MZ8ZZTRTS17`
- Identity name: `OkinawaDesktopTools.OfflineNotesCanary`
- Current submission: draft `1152921505702251319`
- Product state shown on Overview: `In draft`

The publisher, PFN, and Package SID were also read from Product Identity and
matched the existing local reference. They are not duplicated in this screen
mapping because the immutable handoff remains the authoritative input.

## Exact observed routes and semantics

| Section | Route suffix | Exact heading / control | Observation |
|---|---|---|---|
| Overview | `/overview` | `Application overview` | One current draft; Submit for certification disabled |
| Identity | `/identity` | `Product Identity` | Store ID and Identity visible |
| Pricing | `/submissions/<draft>/availability` | `Pricing and availability` / `Save draft` | Base price is not configured |
| Properties | `/submissions/<draft>/properties` | `<Product> | Properties` / `Save` | Category and privacy declaration are unselected |
| Age ratings | `/submissions/<draft>/ageratings/edit` | `Age ratings` / `Save draft` | Dynamic IARC questionnaire; no answer changed |
| Packages | `/submissions/<draft>/packages` | `<Product> | Packages` / `Save` | Empty upload area; no package selected |
| Store listings | `/submissions/<draft>/managelanguages?ProductType=App` | `Manage Store listing languages` / `Save` | Languages appear after package upload |
| Submission options | `/submissions/<draft>/options` | `<Product> | Submission Options` / `Save` | Save disabled; no value changed |

## Verified package-page selectors

- File input: `input[name='fileuploader'][type='file'][multiple]`
- Current draft link: exact `Packages` navigation link with a route ending in
  `/packages`
- Save control: role `button`, exact accessible name `Save`

The following remain intentionally unverified until a separately authorized
upload is performed with a fully evidenced package:

- uploading / validating / valid / warning / error exact DOM states
- package-section complete versus incomplete state
- Save success signal
- post-reload package row and version signal
- Overview completion signal for all six required sections

Consequently `PARTNER_CENTER_MAP.json` keeps `write_enabled=false`. The live
runner fails before connecting to the browser while any required write-state
selector is unverified.

## Safety conclusions from this observation

- Product name alone is insufficient; Store ID and Product Identity must be
  read and matched before a package write.
- Package validation and Packages-section completion are separate evidence.
- A package upload cannot prove `DRAFT_SAVED`; Save and reload verification plus
  all required section states are mandatory.
- The observed product is not currently eligible for upload: the central
  handoff has no bound request/source SHA or real local MSIX, and Store
  submission authorization is false.
- No automation path in this repository clicks Submit for certification or
  Publish.
