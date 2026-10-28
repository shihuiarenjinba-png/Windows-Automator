# Partner Center 申請ルートテンプレート

Partner Center の `New product` で表示される4種類を、Windows-Automatorでは固定テンプレートとして扱う。

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

ユーザーは最初に申請種類を1つ選ぶ。

その選択から自動的に:
1. app/gameを決定
2. 固定プリセットを適用
3. 必要入力項目を決定
4. AI補完可能項目を決定
5. package validation方式を決定
6. Partner Centerの申請経路を決定
7. live adapterを決定

AIはテンプレートを変更しない。AIはテンプレートが許可した入力欄だけを補完する。

セキュリティ・Identity・Store ID・package provenanceはAI確定禁止。
