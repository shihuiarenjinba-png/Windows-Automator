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

本番selectorは推測せず、実画面確認後だけ有効化します。現時点はdraft準備・dry-runまでで、Submit for certificationは自動化しません。

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

現在の「下書きアップロード」は無効です。Partner Center実画面のselectorをコード担当が確認し、誤操作防止条件を満たした後に有効化します。
