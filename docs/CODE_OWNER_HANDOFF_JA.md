# コード担当引継ぎ — Windows-Automator / Microsoft Store Submission Manager v0.6

## 役割
3つの支援ツールのうち「③ Microsoft Storeへ実際に登録する自動化」を担当します。IdentityやStore IDは前段の照合結果を受け取り、このツールでは推測しません。

## 現状
- 通常UIはアプリ/ゲーム、製品名、GitHub、製品内容、MSIX/MSIXUPLOAD、画像、価格だけを主入力にします。
- Yes/No、カテゴリ、ゲームジャンル等は裏側で自動選択します。Microsoft側の選択肢そのものは編集不可です。
- 空欄は `ollama`（補完対象）/ `blank`（意図的空欄）/ `review`（人間確認）を区別します。
- GitHub tokenはGitHub API読取だけに使用し、Ollamaへ渡しません。
- IARCなど動的設問は、Partner Centerに現在表示された質問文と選択肢を取得し、その選択肢内だけからOllamaに選ばせます。
- パッケージは `.msix/.msixupload/.msixbundle/.appx/.appxupload/.appxbundle` を扱います。
- 夜間キューは1製品のHOLD/ERRORで全体停止しません。認証切れのみ全体停止します。書込結果不明はUNKNOWNとして同じ製品を自動再送しません。
- 最終認定提出はまだ自動化しません。まずSave draftまでです。

## Partner Center実画面で次に確認すること
1. Apps and gamesから製品を検索/選択するselector。
2. Pricing and availability: markets, visibility, pricing, free trial。
3. Properties: category/subcategory/genre, privacy, game settings, declarations。
4. Age ratings: IARCの現在表示質問と選択肢のDOM取得、条件分岐。
5. Packages: file input、upload進捗、validation成功/失敗表示。
6. Store listings: Description、What's new、Features、screenshots。
7. Submission options: publishing hold、certification notes、restricted capability説明。
8. Save完了状態。Submit for certificationは押しません。

## セレクター規則
- 座標クリック禁止。
- role/label/textなど意味ベースを優先。
- Yes/Noなどはexact matchのみ。fuzzy match禁止。
- 固定sleepだけで進めず、画面遷移/保存完了/validation完了を待つ。

## 実機QA
最初は一般アプリ1件＋ゲーム1件。Product ID/Identityの一致を確認してからdraft更新。パッケージvalidation失敗はその製品HOLD→次へ。認証切れは全体停止。

## GitHubルール
main/release直書き禁止。作業ブランチで変更し、Windows GitHub Actionsでテスト。token/secretはcommitしない。


## Scheduled API Runner — Private Store署名QA lane

Scheduled API Runnerは、未署名exact EXEのone-shot確認でWindows Application Controlにより起動前ブロックとなり、中央側で

`PRIVATE_STORE_SIGNING_LANE_READY`

まで完了しています。

この製品についてはFolder用handoffを流用しないでください。

専用handoff:

`docs/SCHEDULED_API_RUNNER_STORE_SIGNING_HANDOFF_20261118.md`

read-only観測テンプレート:

`docs/SCHEDULED_API_RUNNER_PRIVATE_ACQUISITION_OBSERVATION_TEMPLATE_20261118.json`

checkpoint:

`docs/SCHEDULED_API_RUNNER_PRIVATE_SIGNING_CHECKPOINT_20261118.json`

zero-cost route classifier:

`scripts/classify_private_store_acquisition.py`

重要:

- Private audienceだけでは有料アプリが無料になるとは限らない。
- paid checkoutが表示されたら購入せずHOLD。
- Promo code生成・一時Free変更・package upload・certification・Private publishはそれぞれ別approval。
- Frozen candidateを再ビルド/差替えしない。
- 未署名EXEを再起動しない。
- Store署名済みPrivate版取得後にのみGUI/DPI/HTTPS/CSV/Task Scheduler QAを再開する。

## 完了報告
repo / branch / start HEAD / final HEAD / PR / tests / Windows GUI / Partner Center mapping / 実アップロード有無 / HOLDを記録してください。
