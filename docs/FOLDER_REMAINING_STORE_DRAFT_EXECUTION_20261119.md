# Folder Automation Engine — Complete the remaining Store Draft sections

Date: 2026-11-19 JST

## Goal

Continue the already-existing Partner Center Draft for **Folder Automation Engine**
from the current state:

- Store ID: `9P99MJX1R4V6`
- Draft ID: `1152921505702423660`
- Source SHA: `adfc0d08efb0a94602d5286557d399f9cb28b9dd`
- Exact MSIX SHA-256: `3C6BC8C1291450905AE71834F2704A59325D1AAA1C9DE3F064BCB8C7EBCA9FB9`
- Exact EXE SHA-256: `DE6894AE39CBE0FBE1889B4AA005E500F30A2EF95EE67403DDFB210DBCFB9F18`
- Version: `1.0.0.0`
- Architecture: `X64`
- Packages: `Complete`, Microsoft validation `Validated`
- Pricing and availability: `Complete`
- Package upload attempts: 1
- Known package warning: exact `runFullTrust` warning only
- Private QA Known User Group: `Folder Automation Engine Private QA`, member count 1

Do not re-upload the package. Do not repeat Start submission.

The next target is:

`STORE_DRAFT_COMPLETE`

with all required sections Save/reload verified.

Certification and Publish are still prohibited in this task.

---

## Required remaining order

1. Properties
2. Age ratings / IARC
3. Store listings
4. Submission Options
5. Overview reconcile
6. Reload/reopen and prove all six required sections Complete

Do not submit for certification.

---

# 1. Properties

## Evidence-backed product facts

Folder Automation Engine is a packaged Win32 desktop app that:

- works with local folders selected by the user;
- previews matching files before writes;
- copies or moves local files only after explicit confirmation;
- can save/load local JSON configuration;
- can keep local processing history;
- can optionally monitor a selected folder while the app is open;
- has no product account/login;
- has no implemented cloud API;
- has no implemented telemetry/analytics;
- has no ads;
- does not use camera, microphone or location;
- declares `runFullTrust`.

## Primary category

Observe the actual current Partner Center category options.

Preferred candidate:

`Utilities & tools`

Use it only if that exact option exists and the live form semantics match this desktop
file-organization utility.

If the exact option is absent or the live taxonomy materially differs:

`HOLD_CATEGORY_REVIEW`

Do not invent a category label.

Secondary category/subcategory is optional unless Partner Center requires it.

## Personal information question

The repository privacy analysis states that the app can access user-selected file
paths, file names, metadata and file contents. Those values can contain personal
information.

Therefore, for the Partner Center question equivalent to:

`Accesses, collects, or transmits personal information`

the evidence-backed answer is:

`YES`

Do not misrepresent the app as never accessing personal information merely because
the app does not transmit it externally.

Microsoft's current MSIX support-info guidance states that when this answer is Yes,
a privacy policy is required. It also states that, when a hosted URL is not
available, Partner Center can accept privacy-policy text directly.

Preferred order:

1. If the live Properties page offers inline privacy-policy text, enter the approved
   policy text derived from `store/PRIVACY_POLICY.md`.
2. If the live form only accepts a URL, stop with
   `HOLD_PRIVACY_POLICY_PUBLIC_URL_REQUIRED`.

Do not create or guess a public privacy URL.

## Privacy policy content facts

The policy must preserve these verified facts:

- file/folder access is local and user-selected;
- no publisher telemetry or analytics;
- no advertising;
- no account sign-in;
- no app-controlled file upload;
- no credential transmission;
- app-created preferences and processing state are local;
- a third-party cloud-synced folder may independently sync according to that
  provider's terms.

Do not silently state that uninstall always deletes LocalState unless the final
Store-signed uninstall behavior has been proven.

## Website / support

Website is optional.

For any required support contact, preserve an existing owner-approved support value
if Partner Center already contains one. Do not invent a new email/domain.

If the field is required and no approved support destination is available:

`HOLD_SUPPORT_CONTACT_REQUIRED`

## Product declarations / capabilities

Answer from exact implementation and package evidence only.

Known current facts:

- local file/folder access: YES
- external app-controlled network/cloud service: NO
- external account/login: NO
- camera: NO
- microphone: NO
- location: NO
- driver/service dependency: NO
- restricted capability: `runFullTrust`

Unknown/new declaration -> HOLD rather than guess.

## System requirements

Evidence candidate:

- Windows 10/11 Desktop
- x64
- package target minimum Windows version: `10.0.19041.0`

Do not add CPU/RAM/GPU requirements that are not supported by evidence.

## Properties Save contract

After entering only supported values:

1. click Save once;
2. return to Overview;
3. require Properties = `Complete`;
4. reopen/reload Properties;
5. verify exact retained values;
6. verify dirty/unsaved state is false.

Success:

`PROPERTIES_SAVED`

Any ambiguous navigation/save result:

`HOLD_PROPERTIES_RECONCILE_REQUIRED`

---

# 2. Age ratings / IARC

The app needs an IARC rating on first submission.

Do not copy answers from Folio, Daymark or any game.

Read every currently displayed IARC question because IARC may change the
questionnaire.

## Evidence-backed content profile

The current product itself contains no implemented:

- violence;
- blood/gore;
- sexual content;
- nudity;
- strong language;
- controlled-substance content;
- gambling;
- simulated gambling;
- loot boxes;
- user-generated social content;
- public chat or online communication;
- location sharing;
- in-app purchases;
- external web content feed;
- account-based online interaction.

It is an offline local file utility.

Use those facts only when they map exactly to the live question.

If the question semantics differ, HOLD rather than reinterpret aggressively.

## IARC workflow

1. Open Age ratings for Draft `1152921505702423660`.
2. Capture the current displayed questionnaire.
3. Map each question to source/package evidence.
4. Complete evidence-backed questions.
5. Generate/preview the resulting rating.
6. Record the generated rating result.

### Owner/legal boundary

The final IARC confirmation may include acceptance of IARC terms and a personal
attestation that the signer is of legal age.

Automation must not invent that attestation.

When that checkbox/confirmation is reached:

`OWNER_INPUT_REQUIRED_IARC_LEGAL_ATTESTATION`

After the owner performs or explicitly authorizes that personal attestation, continue.

Then:

- Save / Save and generate;
- return to Overview;
- require Age ratings = `Complete`;
- reopen/reload;
- prove the generated rating is retained.

Success:

`IARC_SAVED`

---

# 3. Store listings

Current package languages observed:

- `ja-jp`
- `en-us`

Do not remove a package language.

Create/complete both Japanese and English listings.

## Japanese

Product name:

`Folder Automation Engine`

Short description:

`条件に合うローカルファイルを、試運転で確認してから安全にコピー・移動するWindowsアプリです。`

Description:

`Folder Automation Engineは、選択したフォルダー内のファイルを、ファイル名パターン（例：*.pdf）に従って別のフォルダーへコピーまたは移動するオフラインツールです。

メインフォルダー、入力先、保存先、条件を設定し、書き込みを行わない「変更せず確認」で対象を確認してから、明示的な確認操作で1回実行します。最大10件の規則を設定でき、設定JSONを任意の場所へ新規保存して、後から読み込めます。読み込み後や対象ファイルの変更後は、再度プレビューが必要です。

既存の保存先ファイルは上書きしません。任意の自動整理機能は、承認済みの規則と安定した入力だけを処理し、停止操作またはアプリ終了で停止します。アプリは外部サービスへデータを送信せず、広告・分析・アカウントログインも使用しません。

処理前にプレビュー結果と保存先を確認してください。アプリは通常のローカルフォルダーを対象とし、リンク経由のフォルダーや既存ファイルへの意図しない上書きを避ける安全確認を行います。`

Features:

- `書き込みを行わないプレビュー`
- `明示確認後の1回コピー／移動`
- `最大10件のファイル名規則`
- `既存ファイルを上書きしない安全設計`
- `設定JSONの保存と安全な再読み込み`
- `任意のフォルダー自動整理と停止`
- `日本語／英語UIとローカル言語設定保存`
- `外部通信・広告・分析なし`

Developed by:

`Okinawa Desktop Tools`

## English

Product name:

`Folder Automation Engine`

Short description:

`Preview, then safely copy or move local files by filename rules—fully offline on Windows.`

Description:

`Folder Automation Engine is an offline Windows tool for copying or moving files from a selected folder according to deterministic filename patterns such as *.pdf.

Choose a root folder, input and destination folders, and rules. Review a no-write Preview without changes, then explicitly confirm a one-time operation. Up to 10 rules are supported. You can save a new configuration JSON file in a location you choose and safely load it later. Loading a configuration or changing the input files invalidates the previous preview and requires a new preview.

Existing destination files are never overwritten. Optional automatic organizing uses the approved rules and processes stable input only; it stops when requested or when the app closes. The app has no external data transmission, ads, analytics or account sign-in.

Review the preview and destination before processing. The app is designed for regular local folders and validates paths to avoid redirected folders and unintended overwrites of existing files.`

Features:

- `No-write preview before processing`
- `Explicitly confirmed one-time copy or move`
- `Up to 10 filename rules`
- `No overwrite of existing destination files`
- `Save and safely reload configuration JSON`
- `Optional automatic organizing with a clear stop action`
- `Japanese and English UI with local language preference`
- `No external network communication, ads or analytics`

Developed by:

`Okinawa Desktop Tools`

## Screenshots

Use only genuine screenshots from the exact
`adfc0d08efb0a94602d5286557d399f9cb28b9dd` candidate.

Current approved candidate setup images are 1366x768:

- Japanese setup screenshot from Store-listing candidate run `44269998298`
- English setup screenshot from Store-listing candidate run `44269998298`

At least one screenshot is required by the current Microsoft listing requirements;
Microsoft recommends more. For the first Private Audience signing lane, do not invent
additional screenshots. Add genuine additional images only if they exist from the
same exact candidate.

For each screenshot upload:

1. one file at a time;
2. wait for Desktop screenshot count + thumbnail count to increase exactly by one;
3. on timeout, reload/reconcile before retrying;
4. never duplicate one image because the UI response was slow.

## Store listing Save contract

For each language:

- exact description retained;
- exact screenshot count retained;
- screenshot count > 0;
- language state = `Complete`;
- dirty state false after reload.

After both languages:

- Overview Store listings = `Complete`;
- reopen/reload and prove both language rows remain `Complete`.

Success:

`LISTING_SAVED`

---

# 4. Submission Options

Use manual publish hold.

Select the live option equivalent to:

`Don't publish this submission until I select Publish now`

This is critical because certification must not automatically publish the product.

## Certification notes

Use a concise factual note such as:

`Folder Automation Engine is an offline Windows desktop file-organization utility. It does not require an account or network connection. To test it, select a disposable local root folder containing separate input and destination subfolders, choose a filename pattern, run Preview without changes, then Confirm and run. Existing destination files are not overwritten. Optional automatic organizing runs only while the app is open.`

Do not include secrets or private filesystem paths.

## Restricted capability: runFullTrust

Use the exact package-bound, owner-confirmed explanation only.

Recommended text:

`Folder Automation Engine is a packaged Win32 desktop app. runFullTrust is required so the desktop executable can work with folders explicitly selected by the user, perform local copy or move operations, keep local processing state, and run the optional in-process folder watcher while the app is open. It is not used for administrator elevation or to modify or bypass Windows security settings.`

Before write:

- confirm the exact uploaded package still declares `runFullTrust`;
- confirm the explanation is bound to
  `3C6BC8C1291450905AE71834F2704A59325D1AAA1C9DE3F064BCB8C7EBCA9FB9`.

Unknown restricted capability -> HOLD.

## Submission Options Save contract

After Save:

- same Draft;
- Overview Submission Options = `Complete`;
- reload;
- manual publishing hold retained;
- runFullTrust text retained exactly;
- dirty state false.

Success:

`SUBMISSION_OPTIONS_SAVED`

---

# 5. Final Overview reconcile

After all remaining sections succeed, Overview must show the required six sections
Complete:

1. Pricing and availability = Complete
2. Properties = Complete
3. Age ratings = Complete
4. Packages = Complete
5. Store listings = Complete
6. Submission Options = Complete

Then:

1. reload/reopen Overview;
2. verify same Store ID / Draft ID;
3. verify package remains `1.0.0.0 / X64 / Windows.Desktop / Validated`;
4. verify no new Microsoft warning/error;
5. verify all six sections remain Complete.

Final state:

`STORE_DRAFT_COMPLETE`

Then convert to:

`READY_FOR_CERTIFICATION_REVIEW`

only as a review state.

Do not click Submit for certification in this task.

---

# 6. Live-write implementation requirement

Current Windows-Automator has proven package upload and restricted-capability
Submission Options persistence. Properties, IARC and Store listings must not be
implemented by guessing selectors.

For each still-unproven section:

1. inspect the live Partner Center page first;
2. record exact visible labels/roles/selectors;
3. implement one narrow route mapping;
4. add unit/fixture tests;
5. perform the actual write once;
6. Save;
7. return to Overview;
8. reload/reopen;
9. verify persistence;
10. only then mark the selector/route mapping as verified.

Never generalize a Folder-specific value into a route default.

Route-level reusable behavior may include:

- Save/reload reconciliation;
- language-row handling;
- one-image-at-a-time screenshot upload;
- IARC displayed-question enumeration;
- manual-publish-hold selection;
- exact restricted capability persistence.

Product-specific data remains product-specific.

---

# 7. Current external state

Known User Group:

`Folder Automation Engine Private QA`

Type:

`Known user group`

Current member count:

`1`

Do not create another group.

Pricing is already Complete; do not rewrite it.

Package is already uploaded and retained; do not re-upload it.

---

# 8. Safety boundaries

Start submission:

`DO NOT REPEAT`

Package upload:

`DO NOT REPEAT`

Certification:

`NOT AUTHORIZED`

Publish:

`NOT AUTHORIZED`

Unknown Partner Center warning/error:

`HOLD_UNKNOWN_MICROSOFT_RESPONSE`

Session expired:

require human sign-in, then reload/reconcile before any write.

---

# 9. Required final report

## Properties
- live fields observed:
- category:
- personal-information answer:
- privacy policy mode:
- Save:
- reload retained:
- Overview:

## IARC
- live questionnaire captured:
- evidence-backed answers:
- owner legal attestation:
- generated rating:
- Save:
- reload retained:
- Overview:

## Store listings
- ja-JP:
- en-US:
- screenshot counts:
- exact candidate provenance:
- Save:
- reload retained:
- both languages Complete:
- Overview:

## Submission Options
- manual publish hold:
- certification notes:
- runFullTrust:
- Save:
- reload retained:
- Overview:

## Final
- Pricing: Complete
- Properties:
- Age ratings:
- Packages: Complete
- Store listings:
- Submission Options:
- Same Draft ID:
- Package retained:
- Unknown warnings/errors:

Final state must be either:

`STORE_DRAFT_COMPLETE / READY_FOR_CERTIFICATION_REVIEW`

or one precise HOLD code.

Certification:

`NOT EXECUTED`

Publish:

`NOT EXECUTED`
