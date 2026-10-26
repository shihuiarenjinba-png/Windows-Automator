# Partner Center 自動入力仕様

この台帳は、Windows-Automatorの内部データをPartner Centerへ安全に反映するための基準です。

## 自動入力の優先順位

1. **固定プリセット** — アプリ/ゲーム選択時に自動適用
2. **製品固有入力** — MSIX、画像、価格など
3. **セキュリティ必須確認** — AIだけでは確定しない
4. **Ollama候補** — Description、Features、Category候補等
5. **Partner Center実画面** — 現在表示されている選択肢とexact match
6. **Save完了確認** — 完了状態を確認して次へ

## 固定プリセット向き

- 製品種別
- 既存更新 / 新規
- Discoverable
- Free trialなし
- Publishing hold = manual publish
- 既定市場プリセット（運用で固定する場合）

価格額、カテゴリ、IARC、セキュリティ宣言は固定しません。

## Microsoft公開仕様に基づく必須項目

### Pricing and availability
- Markets
- Visibility / discoverability
- Base price

### Properties
- Category
- 個人情報へのアクセス・収集・送信のYes/No
- 個人情報を扱う場合のPrivacy policy

### Age ratings
- 現在表示されるIARC質問すべて

### Packages
- 少なくとも1パッケージ
- Microsoft側validation完了

### Store listings
- 少なくとも1言語
- Description
- 少なくとも1 screenshot

### Submission options
- Restricted capabilityをパッケージが宣言している場合、その利用理由

## AIへ任せられる主な項目

- Description
- Short description
- What's new
- Features
- Category / genre候補
- System requirementsの文章候補
- Certification notes
- Restricted capability理由の文章下書き（Capabilityそのものはパッケージ検出結果を正とする）

## AIだけで確定しない項目

- 個人情報
- 外部ログイン
- 外部通信
- ローカルファイルアクセス
- カメラ / マイク / 位置情報
- Restricted capability有無
- Driver / NT service依存
- IARCで根拠不足の回答
- 価格額
- Store Product ID / Identity

## 実画面マッピング時のルール

- 座標クリック禁止
- exact option match
- 表示中の選択肢以外を生成しない
- 保存完了/validation完了を状態で確認
- selector未確認の項目は本番write不可
- Submit for certificationは別承認まで自動化しない
