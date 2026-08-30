# SITE_Source 共通プログラム

`entrypoint.py` がURLを判定し、対応するサイトフォルダの `*_downloader` へ処理を委譲します。
サイト固有の実処理は共通モジュールを利用し、サイトDBは各サイトフォルダの `database` に保存します。
