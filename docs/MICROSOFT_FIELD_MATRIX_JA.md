# Microsoft Store 入力項目マッピング（MSIX）

更新日: 2026-10-26

この文書は **Microsoftの公開仕様** と **Windows-Automator内部の必須確認項目** を分離するための台帳です。Partner Centerの実画面で文言・選択肢・DOMが確認できるまで、selectorはUNVERIFIEDのままにします。

## 1. Pricing and availability

Microsoft公開仕様上、主に次を扱います。

- Markets — 必須
- Audience — 必須
- Discoverability — 必須
- Schedule — 必須
- Base price — 必須
- Free trial — 任意
- Sale pricing — 任意
- Organizational licensing — 任意

自動化方針:
- 価格、対象市場、公開時期は保存済みプリセットまたは明示入力を優先。
- Ollamaが勝手に価格や市場を確定しない。

## 2. Properties

Microsoft公開仕様上、主に次を扱います。

- Category — 必須
- Subcategory / genre — 条件付き
- Secondary category — 任意
- Personal information access / collection / transmission — 明示回答
- Privacy policy URL — 個人情報を扱う場合は必須
- Website — 任意
- Support / contact information — 条件付き
- Game settings — 任意
- Display mode — 任意
- Product declarations — 条件付き
- System requirements — 任意

### Windows-Automatorで必須にするセキュリティ確認

以下はStore側の1画面1項目と完全一致するとは限りませんが、誤申告を避けるため **内部的に全項目必須** とします。

1. 個人情報へアクセス・収集・送信するか
2. 外部アカウント / ログインを使うか
3. 外部API / クラウドへ通信するか
4. ユーザーのファイル / フォルダへアクセスするか
5. カメラを使うか
6. マイクを使うか
7. 位置情報を使うか
8. 制限付きCapabilityを宣言しているか
9. Microsoft以外のドライバー / NT Serviceへ依存するか

これらはOllamaが候補を作成しても **confirmed=false** のままです。UIで確認後にだけ confirmed=true にします。

確認は選択中のMSIX/MSIXUPLOAD SHA-256へ紐づけます。パッケージ差し替え時は再確認必須です。

## 3. Age ratings / IARC

- 初回または必要時に表示される質問はすべて必須。
- 最初のカテゴリ回答で後続質問が変化する。
- IARCは質問を更新することがある。

自動化方針:
- 質問文を古い固定リストだけで処理しない。
- Partner Centerに現在表示されている質問文と選択肢を取得。
- Ollamaは **表示中の選択肢からのみ** 回答候補を返す。
- 根拠不足はREVIEW。
- IARCの最終回答は保存履歴と差分を残す。

## 4. Packages

- MSIX / MSIXUPLOAD等をアップロード。
- Microsoft側のvalidation完了を待つ。
- Identity / Store Product IDの照合は別ツールの確定値を使用し、このツールでは推測しない。
- パッケージからrestricted capabilityが検出された場合、事前セキュリティ回答と比較する。
- 不一致ならHOLD。

## 5. Store listings

主な内容:

- Description — 必須
- Screenshot — 少なくとも1枚
- Store logo — 必須
- Features — 任意
- What's new — 任意
- Additional assets — 任意
- Trailer — 任意

自動化方針:
- Description / Features / What's new はOllama補完可。
- 生成値はUIに表示してからStore入力データへ反映。
- 動画は未設定なら完全スキップ。

## 6. Submission options

主な内容:

- Notes for certification — 任意
- Publishing timing / hold — 任意
- Restricted capability explanation — パッケージで検出された場合は必要

自動化方針:
- Restricted capabilityの存在はAI推測で決めない。
- パッケージ検出結果を正とする。
- 利用理由の説明文は、確認済みCapabilityとアプリ内容を根拠にOllamaで下書き可能。
- Submit for certificationは現在自動化対象外。まずSave draftまで。

## AI反映パイプライン

1. ユーザー入力
2. GitHub README / docs / manifestの取得
3. MSIX事前検査結果の取得
4. 固定ルール適用
5. Ollamaが文章・選択候補を生成
6. 候補値を内部フィールドへ格納
7. セキュリティ項目はconfirmedが必要
8. Microsoft実画面の現在の選択肢と突合
9. exact matchできる項目のみ入力
10. Save完了を確認
11. 次セクション / 次製品へ進む

## 公式資料

- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/create-app-submission
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/enter-app-properties?pivots=store-installer-msix
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/support-info
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/age-ratings
- https://learn.microsoft.com/windows/apps/package-and-deploy/app-capability-declarations
- https://learn.microsoft.com/windows/apps/publish/store-policies
