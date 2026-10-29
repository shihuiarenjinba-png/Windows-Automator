# Partner Center 申請ルートテンプレート

Partner Center の `New product` で表示される4種類を、Windows-Automatorでは固定テンプレートとして扱う。

`submission_route` は上流工程が確定した不変値であり、通常のhandoffではAutomator側から変更しない。読み込み優先順位は、上流handoff、ローカルpackage検査（比較専用）、旧JSON互換既定値、手動製品の明示選択の順とする。旧JSONはapp→`msix_pwa_app`、game→`msix_pwa_game`だけを許し、GDK/EXEは推測しない。

経路とpackageが一致しない場合はrouteを書き換えず、`SUBMISSION_ROUTE_PACKAGE_MISMATCH` で製品HOLDにする。

## 1. MSIX or PWA app

内部ID: `msix_pwa_app`

対象:
- 一般アプリ
- MSIX / MSIXUPLOAD / MSIXBundle / AppX 系
- PWA系は同じPartner Center分類だが、PWA固有の実アップロード挙動は実画面で別途確認する

固定:
- app
- discoverable
- free trial = none
- publish hold = manual publish
- 既定市場 = all_markets

製品ごと:
- package
- screenshots
- price
- security profile
- category
- description等

現在のREAD_ONLY Partner Center観測はこのルートで行われている。

## 2. EXE or MSI app

内部ID: `exe_msi_app`

Partner CenterではStoreへEXE/MSIファイルを直接アップロードするのではなく、バージョン固定されたHTTPS installer URLとinstaller metadataを登録する別経路。

必須テンプレート入力:
- ローカルEXE/MSI（QA用）
- HTTPS package URL
- EXE / MSI
- architecture
- silent install arguments
- language
- screenshots
- security
- pricing

このlive経路は未実証なので、専用selector mapが完成するまで自動書込み禁止。

## 3. GDK game

内部ID: `gdk_game`

対象:
- Win32 PC gameをGDKでStore公開
- PC package = MSIXVC / MSIXVC2

テンプレート:
- Game setup
- package
- EKB
- symbols
- submission validator
- Properties
- Age ratings
- Store listings
- Pricing and availability

現在のWindows-AutomatorのMSIX App selectorを流用しない。
GDK専用の実画面/API/MakePkg upload経路を観測してからlive有効化する。

## 4. MSIX or PWA game

内部ID: `msix_pwa_game`

対象:
- 既存UWP/MSIX game
- PWA game

アプリ用MSIXと共通する部分はあるが、game genre / IARC / game propertiesを別テンプレートとして保持する。
ゲーム専用live mapping確認前は自動書込み禁止。

## 共通処理

通常は上流工程で確定した申請種類を `[上流工程で確定済み]` として読取専用表示する。手動製品だけは最初に申請種類を1つ選ぶ。

その選択から自動的に:
1. 上流routeとpackage type/SHAを比較
2. app/gameとの整合を確認
3. 固定プリセットを適用
4. 必要入力項目とroute固有セクションを決定
5. AI補完可能項目を決定
6. package validation方式を決定
7. Partner Center adapterとselector mapを決定

AIはテンプレートを変更しない。AIはテンプレートが許可した入力欄だけを補完する。

セキュリティ・Identity・Store ID・package provenanceはAI確定禁止。

## Live書込みの状態

- `msix_pwa_app`: READ_ONLY観測あり。ただしvalidation/save/reloadのselector evidenceが未完成なため、同梱mapは `live_write_supported=false`。
- `exe_msi_app` / `gdk_game` / `msix_pwa_game`: 専用実画面map未検証。`LIVE_ROUTE_NOT_VERIFIED` でブラウザー書込み前に製品HOLD。
- selector mapはschema 3でroute別に管理し、別routeのselectorを流用しない。
- package validationの `WARNING` はHOLD。`VALID` かつrequired sectionの保存証跡が揃った場合だけ `DRAFT_SAVED`。
- certification submit / publishは自動操作対象外。
