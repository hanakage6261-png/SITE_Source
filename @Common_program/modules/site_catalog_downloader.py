from __future__ import annotations

import argparse
import copy
import re
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from yt_dlp import YoutubeDL

_SYSTEM_ROOT = Path(os.environ.get("SITE_SOURCE_SITE_ROOT", Path(__file__).resolve().parents[2])).resolve()
_DATABASE_MODULES = Path(__file__).resolve().parent
sys.path.insert(0, str(_DATABASE_MODULES))
import site_media_catalog as catalog


# Prefer the highest-quality separate video and audio streams.  MKV is used
# for the merge so AV1, VP9, Opus, and other codecs are not discarded merely
# to keep an MP4 compatibility preference.
DEFAULT_FORMAT = "bestvideo+bestaudio/best"
DEFAULT_MERGE_CONTAINER = "mkv"
OWNER_FIELDS = ("uploader", "uploader_id", "channel", "channel_id", "creator")
MARKDOWN_URL_RE = re.compile(r"^\[[^\]]*\]\((https?://[^)]+)\)$")


def read_urls(files: list[str]) -> list[str]:
    values = []
    for filename in files:
        path = Path(filename).expanduser()
        if not path.is_file():
            raise ValueError(f"URLファイルがありません: {path}")
        for encoding in ("utf-8-sig", "utf-8", "cp932"):
            try:
                lines = path.read_text(encoding=encoding).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"URLファイルを読み込めません: {path}")
        values.extend(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))
    return values


def prompt_urls() -> list[str]:
    print("URLを複数入力できます。空行で入力を終了します。")
    values = []
    while True:
        value = input("URL: ").strip()
        if not value:
            return values
        values.append(value)


def normalize_url(value: str) -> str:
    """Accept a bare URL as well as a Markdown link pasted from chat."""
    value = value.strip().strip("`").strip()
    match = MARKDOWN_URL_RE.fullmatch(value)
    if match:
        value = match.group(1)
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    return value


def parse_cookie_spec(value: str):
    parts = value.split(":", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0],)


def validate_url(url: str, domains: tuple[str, ...]):
    hostname = (urllib.parse.urlparse(url).hostname or "").lower().strip(".")
    if not any(hostname == domain or hostname.endswith("." + domain) for domain in domains):
        raise ValueError(f"対象サイト外のURLです: {url}")


def owner_matches(info: dict, expected: str | None) -> bool:
    if not expected:
        return True
    wanted = "".join(ch.casefold() for ch in expected if ch.isalnum())
    values = []
    for field in OWNER_FIELDS:
        if info.get(field):
            values.append("".join(ch.casefold() for ch in str(info[field]) if ch.isalnum()))
    return wanted in values


def extract(url: str, options: dict) -> dict:
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        # Chrome may keep its Cookies SQLite file locked.  A public video can
        # still be processed without cookies; authenticated items fail later
        # in the normal per-item error path and remain resumable in the DB.
        if "Could not copy Chrome cookie database" not in str(exc):
            raise
        fallback_options = dict(options)
        fallback_options.pop("cookiesfrombrowser", None)
        print("ブラウザCookieを読み込めないため、Cookieなしで再試行します。")
        with YoutubeDL(fallback_options) as ydl:
            info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("動画情報が取得できませんでした")
    return info


def entry_url(entry: dict) -> str | None:
    return entry.get("webpage_url") or entry.get("original_url") or entry.get("url")


def expand_urls(urls: list[str], probe_options: dict, site_id: str) -> list[dict]:
    expanded = []
    seen = set()
    for source_url in urls:
        # Do not probe a direct video twice.  This also makes removed videos
        # produce a normal per-item failure instead of a collection traceback.
        if catalog.source_type(source_url) == "video":
            candidates = [source_url]
            info = {}
        else:
            try:
                info = extract(source_url, {**probe_options, "noplaylist": False, "extract_flat": True})
            except Exception as exc:
                print(f"一覧URLの展開に失敗しました。スキップします: {source_url}\n詳細: {exc}")
                continue
            entries = list(info.get("entries") or []) if info.get("entries") else []
            if entries:
                catalog.save_collection(site_id, source_url, info, entries)
            candidates = [entry_url(entry) for entry in entries] or [source_url]
        for url in candidates:
            if url and url not in seen:
                seen.add(url)
                expanded.append({"url": url, "source_url": source_url})
    catalog.enqueue_many(site_id, expanded)
    return expanded


def output_path(ydl: YoutubeDL, info: dict, template: str, format_selector: str, merge_container: str) -> Path:
    path = Path(ydl.prepare_filename(info, outtmpl=template))
    if "+" in format_selector or info.get("requested_formats"):
        path = path.with_suffix(f".{merge_container}")
    return path


def download_media(url: str, info: dict, options: dict, template: str, format_selector: str, merge_container: str):
    """Download once with cookies, then retry without them if Chrome is locked."""
    attempts = [options]
    if "cookiesfrombrowser" in options:
        fallback = dict(options)
        fallback.pop("cookiesfrombrowser", None)
        attempts.append(fallback)
    last_error = None
    for index, attempt_options in enumerate(attempts):
        try:
            with YoutubeDL(attempt_options) as downloader:
                expected_path = output_path(downloader, info, template, format_selector, merge_container)
                result = downloader.download([url])
            return expected_path, result
        except Exception as exc:
            last_error = exc
            if index == 0 and "Could not copy Chrome cookie database" in str(exc):
                print("実ダウンロードでもブラウザCookieを読めないため、Cookieなしで再試行します。")
                continue
            raise
    raise last_error


def catalog_metadata_item(site_id: str, item: dict, info_options: dict, expected_owner: str | None):
    url = item["url"]
    remote_id = None
    try:
        catalog.queue_update(url, site_id, "metadata")
        info = extract(url, info_options)
        remote_id = catalog.save_item(site_id, info, item.get("source_url") or url)
        catalog.save_streams(site_id, info)
        catalog.save_thumbnails(site_id, info, [])
        if not owner_matches(info, expected_owner):
            raise RuntimeError("expected-owner とメタデータの投稿者が一致しません")
        catalog.queue_update(url, site_id, "cataloged", remote_id)
        return info.get("title") or remote_id, info.get("channel") or info.get("uploader") or info.get("creator") or "-", remote_id, None
    except Exception as exc:
        catalog.queue_failure(url, site_id, exc, remote_id)
        return None, None, remote_id, exc


def catalog_metadata_batch(site_id: str, items: list[dict], info_options: dict, expected_owner: str | None, workers: int):
    batch_size = max(workers * 4, workers)
    for offset in range(0, len(items), batch_size):
        batch = items[offset:offset + batch_size]
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = {
            executor.submit(catalog_metadata_item, site_id, item, info_options, expected_owner): (offset + index, item["url"])
            for index, item in enumerate(batch, 1)
        }
        try:
            for future in as_completed(futures):
                index, url = futures[future]
                title, creator, remote_id, error = future.result()
                if error:
                    print(f"[{index}/{len(items)}] 失敗: {error}")
                else:
                    print(f"[{index}/{len(items)}] {title} / 投稿者: {creator} / ID: {remote_id}")
        except KeyboardInterrupt:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)


def process(site_id: str, site_name: str, base_url: str, domains: tuple[str, ...], argv=None, default_format=DEFAULT_FORMAT, default_container=DEFAULT_MERGE_CONTAINER) -> int:
    # SITE_Source stores code and DBs, never the long-lived media payload.
    media_root = Path(os.environ.get("SITE_SOURCE_MEDIA_ROOT", Path.home() / "Downloads")).expanduser().resolve()
    data_dir = media_root / site_name
    database_dir = _SYSTEM_ROOT / "database"
    media_dir = data_dir
    media_dir.mkdir(parents=True, exist_ok=True)
    database_dir.mkdir(parents=True, exist_ok=True)
    catalog.init_db(database_dir, site_id, site_name, base_url)

    parser = argparse.ArgumentParser(description=f"{site_name} メタデータカタログ付きCLI")
    parser.add_argument("urls", nargs="*", help="動画または一覧URL")
    parser.add_argument("-f", "--url-file", action="append", default=[], help="URL一覧ファイル")
    parser.add_argument("--metadata-only", action="store_true", help="メタデータ・全ストリーム・サムネイル情報だけ保存")
    parser.add_argument("--skip-thumbnails", action="store_true", help="互換用。サムネイル画像は常に取得しません")
    parser.add_argument("--resume", action="store_true", help="DBの未完了キューを再開")
    parser.add_argument("--expected-owner", help="投稿者名の一致を要求")
    parser.add_argument("--cookies-from-browser", "--browser", dest="browser", help="例: chrome または edge:Default")
    parser.add_argument("--cookies", help="Netscape形式cookies.txt")
    parser.add_argument("--format", default=default_format, help="yt-dlp形式指定")
    parser.add_argument("-o", "--output-dir", help="動画保存先。省略時はDownloads/<サイト名>（環境変数で変更可）")
    parser.add_argument("--workers", type=int, default=6, help="メタデータ専用処理の並列数")
    args = parser.parse_args(argv)
    if args.cookies and args.browser:
        parser.error("--cookies と --cookies-from-browser は同時指定できません")
    if args.workers < 1:
        parser.error("--workers は1以上で指定してください")

    explicit_urls = [normalize_url(value) for value in list(args.urls) + read_urls(args.url_file)]
    urls = explicit_urls
    if args.resume:
        urls = catalog.filter_resume_urls(site_id, explicit_urls) + catalog.get_resume_urls(site_id)
    if not urls and not args.resume:
        urls = prompt_urls()
    if not urls:
        print("再開対象のURLがないため終了します" if args.resume else "URLがないため終了します")
        return 0
    for url in urls:
        validate_url(url, domains)

    probe_options = {
        "quiet": True,
        "ignoreerrors": False,
        "skip_download": True,
        "noplaylist": True,
        "js_runtimes": {"node": {}},
    }
    if args.cookies:
        probe_options["cookiefile"] = str(Path(args.cookies).expanduser().resolve())
    elif args.browser:
        probe_options["cookiesfrombrowser"] = parse_cookie_spec(args.browser)

    items = expand_urls(urls, probe_options, site_id)
    print(f"対象URL: {len(items)}件 / DB: {database_dir / catalog.DB_NAME}")
    if args.metadata_only and args.skip_thumbnails and len(items) > 1:
        catalog_metadata_batch(site_id, items, probe_options, args.expected_owner, min(args.workers, len(items)))
        return 0
    template = "%(title).180B [%(id)s].%(ext)s"
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else media_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(items, 1):
        url = item["url"]
        try:
            catalog.queue_update(url, site_id, "metadata")
            info = extract(url, probe_options)
            remote_id = catalog.save_item(site_id, info, item.get("source_url") or url)
            catalog.save_streams(site_id, info)
            # Thumbnail binaries are intentionally never downloaded. The DB keeps
            # the source URL and dimensions so a future UI can choose one.
            catalog.save_thumbnails(site_id, info, [])
            title = info.get("title") or remote_id
            creator = info.get("channel") or info.get("uploader") or info.get("creator") or "-"
            print(f"[{index}/{len(items)}] {title} / 投稿者: {creator} / ID: {remote_id}")
            if not owner_matches(info, args.expected_owner):
                raise RuntimeError("expected-owner とメタデータの投稿者が一致しません")
            if args.metadata_only:
                catalog.queue_update(url, site_id, "cataloged", remote_id)
                continue

            download_options = copy.deepcopy(probe_options)
            download_options.update({
                "quiet": False,
                "skip_download": False,
                "noplaylist": True,
                "format": args.format,
                "paths": {"home": str(output_dir)},
                "outtmpl": {"default": template},
                "windowsfilenames": True,
                "continuedl": True,
                "retries": 20,
                "fragment_retries": 20,
                "merge_output_format": default_container,
            })
            catalog.queue_update(url, site_id, "downloading", remote_id)
            expected_path, result = download_media(url, info, download_options, template, args.format, default_container)
            if result not in (None, 0):
                raise RuntimeError(f"yt-dlp returned {result}")
            catalog.save_local_file(site_id, remote_id, str(expected_path), info)
            catalog.queue_update(url, site_id, "done", remote_id)
            print(f"保存完了: {expected_path}")
        except Exception as exc:
            print(f"[{index}/{len(items)}] 失敗: {exc}")
            catalog.queue_failure(url, site_id, exc, locals().get("remote_id"))
    return 0


def main(site_id: str, site_name: str, base_url: str, domains: tuple[str, ...], argv=None, default_format=DEFAULT_FORMAT, default_container=DEFAULT_MERGE_CONTAINER) -> int:
    return process(site_id, site_name, base_url, domains, argv, default_format, default_container)
