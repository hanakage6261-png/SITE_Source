# SITE_Source移行_Codex指示

## あなたの今回の仕事

現在あなたが作業している:

```text
Original_Systems/01_メディア取得・アーカイブ/動画サイトからのダウンロード
```

配下の既存サイト別ダウンロードシステムを、安全に次へ移行してください。

```text
Original_Systems/SITE_Source/
```

`SITE_Source` は `NASfiles_manage` の内部ではありません。

正式構造:

```text
Original_Systems/
├─ NASfiles_manage/
└─ SITE_Source/
```

両者は同列の独立システムです。

---

# 1. 最重要: SITE_Sourceテンプレートを先に読む

作業開始前に必ず:

```text
Original_Systems/SITE_Source/@sample
```

を確認してください。

さらに、そのフォルダ内の:

```text
指示.txt
```

を必ず読んでください。

各サイトフォルダの構造・配置・命名は、原則として `@sample` と `指示.txt` を正式な参考仕様として扱ってください。

この指示書と `@sample/指示.txt` が矛盾する場合は、勝手に判断せず矛盾点を報告してください。

---

# 2. SITE_Sourceの役割

SITE_Sourceは外部サイトごとの:

```text
ダウンロード
サイトmetadata取得
サイトmetadata DB管理
```

を担当する独立システム。

NASfiles_manageは:

```text
HDD/NAS上に保存済みのローカルファイル管理
```

を担当する別システム。

ただしSITE_Sourceが取得したファイルは、HDD/NASへ保存された後、NASfiles_manageの管理対象になり得る。

---

# 3. 移行先

各サイトは:

```text
Original_Systems/SITE_Source/<サイト名>/
```

として分離してください。

各サイトフォルダには、そのサイト専用の:

```text
program
database file
config
必要な補助ファイル
```

を、`@sample/指示.txt` の構造に従って配置してください。

---

# 4. SITE_SourceにはprogramもDBも置く

SITE_SourceはDBだけの場所ではありません。

各サイトについて:

```text
そのサイト専用ダウンロードprogram
そのサイト専用metadata収集program
そのサイト専用DB
そのサイト専用設定/補助コード
```

をまとめる場所です。

実際にダウンロードされた動画・画像・音楽本体を、SITE_Source内へ長期保存しないでください。

実メディアは現在外付けHDD、将来NASへ保存する前提です。

---

# 5. 既存統合DBをサイト別DBへ分割する

現在のシステムでは、複数サイトのデータが一つのデータベースファイルへまとめられている。

今回の移行ではこれを分割する。

最終状態:

```text
SITE_Source/
├─ SiteA/
│  └─ SiteA専用DB
├─ SiteB/
│  └─ SiteB専用DB
├─ SiteC/
│  └─ SiteC専用DB
└─ ...
```

原則:

```text
1サイト = 1データベースファイル
```

ただし:

```text
1サイト = 1テーブル
```

ではありません。

各サイトDBの中には、そのサイトに必要なだけ複数テーブルを持たせてください。

例:

```text
videos
accounts
tags
video_tags
account_videos
playlists
...
```

---

# 6. DB分割はスキーマを見て安全に行う

現在の統合DBをまず調査してください。

必ず確認:

```text
DB engine
DB file path
全テーブル
各テーブルの役割
主キー
外部キー
中間テーブル
サイト判別列
サイト固有テーブル
複数サイト共有テーブル
```

その上で、各レコード/テーブルをどのサイトDBへ移すべきか決定してください。

名前だけで雑に分割しないこと。

---

# 7. 関係を壊さない

サイト別DBへ分割するとき、以下を維持してください。

```text
動画 ↔ アカウント
動画 ↔ タグ
アカウント ↔ 動画
動画 ↔ プレイリスト
その他既存の関連
```

主キーや外部キーの関係を壊さない。

IDを変更する必要がないなら変更しない。

ID変更が必要な場合は、全参照先を安全に変換し、マッピングを記録する。

---

# 8. 共有テーブル

現在の統合DBに単純に1サイトへ割り当てられない共有テーブルがある場合:

```text
勝手に複製しない
勝手に削除しない
勝手に特定サイトへ所属させない
```

以下へ分類する。

```text
サイトごとに分割可能
共通システムとして残すべき
設計判断が必要
```

設計判断が必要なら報告する。

---

# 9. programもサイト別へ移行

現在の:

```text
Original_Systems/01_メディア取得・アーカイブ/動画サイトからのダウンロード
```

内のprogramを調査し:

```text
どのサイト専用か
共通処理か
どのDBを読む/書くか
どこへファイルを出力するか
ハードコードされたパス
```

を確認してください。

サイト専用programは対応する:

```text
Original_Systems/SITE_Source/<site>/
```

へ移行してください。

内部配置は `@sample/指示.txt` に従う。

---

# 10. 共通処理

複数サイトで共有する処理がある場合、サイトフォルダへ無理にコピーしない。

必要なら:

```text
Original_Systems/SITE_Source/
```

配下の共通領域を設計候補として報告してよい。

ただし今回の主目的は安全な移行。

大規模リファクタリングは避ける。

---

# 11. ダウンロード結果とNASfiles_manage

今回、SITE_SourceとNASfiles_manage自体を統合しない。

しかし長期的には:

```text
SITE_Source
↓
ファイルDL
↓
HDD/NAS
↓
NASfiles_manageがローカルファイルとして登録
```

となる。

さらに将来:

```text
NASfiles_manageのlocal file
↓
source URL
↓
site name
↓
site item ID
↓
SITE_Source/<site>/ のDB
```

を辿れる接続を作る可能性がある。

したがって、サイトDBでは可能な限り:

```text
元URL
サイト固有item ID
```

等の既存情報を失わないこと。

---

# 12. 将来の共通URL受付

将来、SITE_Source側に:

```text
URL
↓
共通受付
↓
対応サイト判定
↓
SITE_Source/<site> のprogramへ処理委譲
```

という入口を作る可能性がある。

今回の移行では実装不要。

各サイトシステムを独立モジュールとして保ち、この将来構造を邪魔しないこと。

---

# 13. メディア出力先

サイト専用ダウンローダーが取得した実メディアをSITE_Source内部へ長期保存しない。

現在:

```text
外付けHDD
```

将来:

```text
NAS
```

へ収容する。

最終保存は元サイト別ではなく内容別整理を基本とする予定。

正式な一時受け入れフォルダはまだ未決定。

勝手に固定しない。

---

# 14. 安全な移行手順

既存システムをいきなり破壊的にMOVEしない。

原則:

```text
1. 現状調査
2. 移行対象一覧
3. 移行先マップ
4. 既存システム/DBバックアップ
5. SITE_Source側へコピー
6. サイト別DB生成
7. データ分割移行
8. DB整合性確認
9. programのDB path等修正
10. 小規模テスト
11. 新環境正常確認
12. 移行レポート
```

元環境は確認完了まで消さない。

---

# 15. DB安全要件

DB移行前:

```text
- 書き込み中でないことを確認
- 元DBをバックアップ
- 元DBを直接破壊的編集しない
```

新サイトDB作成後:

```text
- テーブル一覧確認
- レコード件数確認
- 外部キー/関連確認
- 主要サンプルレコード確認
- SQLiteなら integrity_check
```

パス間違いによる空DB生成を成功と誤認しない。

---

# 16. program path修正

コピーしたprogram内を調査し旧パス参照を確認する。

検索対象例:

```text
01_メディア取得・アーカイブ
動画サイトからのダウンロード
旧統合DB path
旧program path
絶対Windows path
```

無差別置換は禁止。

各パスの役割を確認してから変更する。

---

# 17. DB接続先

移行後、サイト別programは原則として自サイト専用DBだけを読む/書く。

```text
SiteA program
↓
Original_Systems/SITE_Source/SiteA/<SiteA DB>
```

旧統合DBへの書き込みを残さない。

---

# 18. モモンガッSystems

`モモンガッSystems` は今回の一括移行から除外する。

比較的独立した単発/サイト専用ダウンローダー群を先に移行する。

モモンガッSystemsは別プロジェクトで扱う。

---

# 19. 作業前一覧

各移行候補について:

```text
site_name
old_path
entry_program
database_dependencies
tables_used
download_output
config_files
hardcoded_paths
dependencies
migration_risk
```

分類:

```text
MIGRATE_NOW
NEEDS_REVIEW
EXCLUDE
```

モモンガッSystemsは `EXCLUDE`。

---

# 20. 1サイトずつ移行

全部を一発で移行しない。

```text
Site A
↓
コピー
↓
DB分割
↓
path修正
↓
テスト
↓
完了記録
```

の後に次サイトへ進む。

---

# 21. 移行結果レポート

以下を残す。

```text
site
old_path
new_path
old_database
new_database
migrated_tables
record_counts
program_entrypoint
path_changes
test_result
remaining_issues
status
```

status例:

```text
MIGRATED_TESTED
MIGRATED_NEEDS_REVIEW
NOT_MIGRATED
EXCLUDED
```

---

# 22. 今回やらないこと

```text
- Phase1_project変更
- NASfiles_manage内部へSITE_Sourceを移す
- LOCAL_database連携
- file_sources実装
- 共通URL受付実装
- GUI作成
- NAS一時フォルダ最終設計
- モモンガッSystems移行
- 全サイトprogram巨大統合
```

---

# 23. 完了条件

```text
[ ] Original_Systems/SITE_Source/@sample確認
[ ] @sample/指示.txt確認
[ ] 既存サイトシステム一覧化
[ ] モモンガッSystems除外
[ ] 各サイト新フォルダ作成
[ ] @sample準拠
[ ] 各サイトprogram移行
[ ] 元統合DBバックアップ
[ ] サイトごとに独立DB作成
[ ] データを正しいサイトDBへ移行
[ ] リレーション維持
[ ] レコード件数検証
[ ] DB整合性検証
[ ] program DB接続先変更
[ ] 旧absolute path修正
[ ] SITE_Source内部へ実メディアを長期保存しない
[ ] 元URL/site item ID等の既存情報を保持
[ ] 小規模動作テスト
[ ] 元環境を勝手に削除しない
[ ] 移行レポート作成
```

---

# 24. 最重要禁止事項

```text
- @sample/指示.txtを読まず構造を決めない
- SITE_SourceをNASfiles_manage配下へ置かない
- 元統合DBをバックアップせず変更しない
- 元プロジェクトを先に削除しない
- 複数サイトDBを再び1つへまとめない
- 1サイト1テーブルと誤解しない
- リレーションを壊して雑移行しない
- SITE_Sourceへ実メディアを長期保存しない
- モモンガッSystemsを今回触らない
- Phase1_projectを触らない
- 未決定のNAS一時フォルダを勝手に確定しない
```

以上を満たす形で、安全に移行してください。
