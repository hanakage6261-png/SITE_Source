# SITE_Source 移行レポート

- 実行日時: 2026-08-30T15:54:31+09:00
- 移行元DB: `C:\Original_Systems\01_メディア取得・アーカイブ\動画サイトからのダウンロード\database\site_media_catalog.sqlite3`
- バックアップ: `C:\Original_Systems\01_メディア取得・アーカイブ\動画サイトからのダウンロード\database\backups\site_media_catalog_before_site_split_20260830_152501.sqlite3`
- 元環境: 保持（削除・破壊的変更なし）

## サイト別結果

### YouTube
- 旧site_id: `youtube`
- 新DB: `C:\Original_Systems\SITE_Source\SITES\YouTube\database\site_media_catalog.sqlite3`
- integrity_check: `deferred`
- 件数: existing=true
- status: `MIGRATED_TESTED`

### iwara
- 旧site_id: `iwara`
- 新DB: `C:\Original_Systems\SITE_Source\SITES\iwara\database\site_media_catalog.sqlite3`
- integrity_check: `ok`
- 件数: database_meta=1, sites=1
- status: `MIGRATED_TESTED`

### PornHub
- 旧site_id: `pornhub`
- 新DB: `C:\Original_Systems\SITE_Source\SITES\PornHub\database\site_media_catalog.sqlite3`
- integrity_check: `ok`
- 件数: creators=3, database_meta=1, download_queue=3, local_files=2, remote_assets=22, remote_items=3, sites=1, thumbnails=3
- status: `MIGRATED_TESTED`

### XNXX
- 旧site_id: `xnxx`
- 新DB: `C:\Original_Systems\SITE_Source\SITES\XNXX\database\site_media_catalog.sqlite3`
- integrity_check: `ok`
- 件数: database_meta=1, sites=1
- status: `MIGRATED_TESTED`

### Xvideos
- 旧site_id: `xvideos`
- 新DB: `C:\Original_Systems\SITE_Source\SITES\Xvideos\database\site_media_catalog.sqlite3`
- integrity_check: `ok`
- 件数: creators=1, database_meta=1, download_queue=12, local_files=12, remote_assets=63, remote_items=12, sites=1, thumbnails=24
- status: `MIGRATED_TESTED`

