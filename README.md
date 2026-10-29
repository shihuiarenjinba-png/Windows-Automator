# Windows-Automator — Microsoft Store Submission Manager v0.6

Microsoft Storeへのゲーム/アプリ登録作業を、最小入力・固定ルール・GitHub情報・Ollama補完・Partner Center自動操作で短縮するための基盤です。

## 主な入力
- アプリ / ゲーム
- 製品名
- GitHubリポジトリ
- アプリ/ゲームの内容
- MSIX / MSIXUPLOAD
- 商品画像フォルダ
- 価格

Yes/No、カテゴリ、ゲームジャンル等の選択問題は通常UIで毎回操作せず、裏側で決定します。OllamaはMicrosoft側に実際に存在する選択肢からしか回答できない契約です。高影響の宣言は根拠不足ならREVIEWに残します。

## Partner Center申請種類

Partner Centerの `New product` に合わせて、次の4種類を固定テンプレートとして扱います。

- `MSIX or PWA app`
- `EXE or MSI app`
- `GDK game`
- `MSIX or PWA game`

UIで申請種類を選ぶと、app/game区分、固定プリセット、必要入力、許可するパッケージ形式、AI補完対象、Partner Center経路を自動選択します。

- MSIX/PWA app: 現在READ_ONLYで観測済みの標準MSIX経路
- EXE/MSI app: HTTPS installer URL、EXE/MSI、architecture、silent install引数、languageが必要
- GDK game: PCはMSIXVC/MSIXVC2を使用し、EKB/symbols/submission validatorを専用テンプレートで扱う
- MSIX/PWA game: game genre / IARC / game propertiesをゲーム用テンプレートで扱う

未実証のrouteはテンプレートだけを適用し、live Store writeはHOLDします。MSIX App以外のlive mappingをMSIX App selectorで代用しません。

詳細: `docs/SUBMISSION_ROUTE_TEMPLATES_JA.md`

## 夜間処理
製品単位のHOLD/ERRORは記録して次へ進みます。認証切れのみ全体停止。書込成否不明はUNKNOWNにし、同じ製品を自動再送しません。朝にJSON/Markdownレポートを確認します。

## Partner Center
公式申請フローを次の6区分で扱います。
1. Pricing and availability
2. Properties
3. Age ratings
4. Packages
5. Store listings
6. Submission options

本番selectorは推測せず、実画面確認後だけ有効化します。ライブ実行のコード経路は追加済みですが、実アップロードでvalidation/Save/再読込のDOMを観測するまでは selector map が `write_enabled=false` のためfail-closedです。Submit for certification / Publishは自動化しません。

## Test
```powershell
python -m unittest discover -s tests -v
```

## Official references
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/create-app-submission?pivots=store-installer-msix
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/price-and-availability
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/enter-app-properties?pivots=store-installer-msix
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/age-ratings
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info
- https://learn.microsoft.com/windows/apps/publish/msstore-dev-cli/overview


## Windows GUI

起動:

```powershell
python -m store_manager.gui
```

通常操作は4画面です。

1. **製品とファイル** — アプリ/ゲーム、製品名、GitHub、内容、MSIX/MSIXUPLOAD、画像、価格
2. **自動入力・要確認** — 裏側で選ばれたStore回答を確認。普段は触らず、修正が必要な行だけダブルクリック
3. **夜間キュー** — 複数製品を並べ、HOLDがあっても次製品へ進む前提で事前確認
4. **結果・設定** — DONE/HOLD等のレポート、Ollama URL/model、GitHub token入力

GitHub tokenはGUIから保存せず、GitHubコンテキスト取得だけに使用し、Ollamaへ渡しません。

現在の「下書きアップロード」は安全側で無効です。読み取り観測済みの画面契約は `docs/PARTNER_CENTER_SCREEN_MAPPING_20261029.md`、機械可読selectorは `docs/PARTNER_CENTER_MAP.json` を参照してください。

ライブ経路を使うには、Store ID / source SHA / package SHA / Identity / Version、Windows-checker合格、人間の軽量QA、検証済みselector map、既存のログイン済みブラウザがすべて必要です。さらに実行時に `--execution-mode live --confirm-live-draft --cdp-url <endpoint>` を明示します。`DONE` はDry Runだけ、Save後の再読込と全セクション証拠を満たした場合だけ `DRAFT_SAVED` です。

Playwrightは任意依存です。

```powershell
py -3.11 -m pip install -e ".[live]"
```


## Optional trailers

Video is **optional**. The normal workflow does not show trailer controls and does not warn when no trailer is configured.

If a trailer is intentionally added from **詳細設定 → 動画設定**, validation is enabled for that trailer only:
- MP4 or MOV video
- title
- PNG thumbnail
- for game listings using a trailer, 16:9 Super hero art

If no trailer is configured, the Partner Center plan skips all trailer upload actions.
