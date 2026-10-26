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
