# SITE_Source

`@Common_program\run_site_source.bat` が唯一の起動入口です。URLを判定し、`SITES\<サイト名>\<サイト名>_downloader` へ処理を委譲します。

各サイトのDBは各サイトフォルダの `database` に分離されています。実メディアはSITE_Source内へ長期保存せず、既定では `Downloads\<サイト名>` へ保存します。将来NASの一時フォルダへ切り替える場合は、実行前に `SITE_SOURCE_MEDIA_ROOT` 環境変数へ保存先を設定します。

サムネイル画像ファイルは取得せず、DBにはURL・幅・高さ・形式・表示順などの情報だけを保存します。

## Gitの管理範囲

このリポジトリは共通基盤です。`@Common_program`、`develop`、共通設計書だけを管理します。
`SITES`配下の各サイト別システムは、それぞれ独立したGitリポジトリとして管理するため、このリポジトリでは追跡しません。
