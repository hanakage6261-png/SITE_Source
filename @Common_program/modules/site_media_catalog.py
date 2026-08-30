from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path


DB_NAME = "site_media_catalog.sqlite3"
MAX_RETRIES = 3
_BASE_DIR: Path | None = None


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_text(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def compact_info(info: dict | None) -> dict:
    excluded = {"formats", "thumbnails", "entries", "requested_formats", "requested_downloads"}
    return {key: value for key, value in (info or {}).items() if key not in excluded}


def source_type(url: str | None) -> str:
    value = (url or "").lower()
    if any(token in value for token in ("playlist", "list=", "favorite", "favourites", "liked", "likes", "watchlater", "watch-later")):
        return "playlist"
    if any(token in value for token in ("/channel/", "/user/", "/profile", "/profiles/", "/feed/")):
        return "channel"
    return "video"


def init_db(base_dir: str | os.PathLike[str], site_id: str, site_name: str, base_url: str):
    global _BASE_DIR
    _BASE_DIR = Path(base_dir).resolve()
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS database_meta (
                key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sites (
                site_id TEXT PRIMARY KEY, name TEXT NOT NULL, base_url TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS creators (
                site_id TEXT NOT NULL, creator_key TEXT NOT NULL, name TEXT,
                creator_url TEXT, uploader_id TEXT, metadata_json TEXT,
                first_seen_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(site_id, creator_key)
            );
            CREATE TABLE IF NOT EXISTS remote_items (
                site_id TEXT NOT NULL, remote_id TEXT NOT NULL, canonical_url TEXT,
                webpage_url TEXT, title TEXT, description TEXT, upload_date TEXT,
                timestamp INTEGER, duration REAL, creator_key TEXT, creator_name TEXT,
                creator_url TEXT, uploader_id TEXT, age_limit INTEGER, availability TEXT,
                language TEXT, license TEXT, tags_json TEXT, categories_json TEXT,
                chapters_json TEXT, subtitles_json TEXT, automatic_captions_json TEXT,
                metadata_json TEXT, filename_stem TEXT, first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, metadata_check_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(site_id, remote_id)
            );
            CREATE TABLE IF NOT EXISTS remote_assets (
                site_id TEXT NOT NULL, remote_id TEXT NOT NULL, asset_id TEXT NOT NULL,
                asset_type TEXT NOT NULL, ext TEXT, protocol TEXT, format_name TEXT,
                vcodec TEXT, acodec TEXT, width INTEGER, height INTEGER, fps REAL,
                tbr REAL, vbr REAL, abr REAL, asr INTEGER, filesize INTEGER,
                filesize_approx INTEGER, dynamic_range TEXT, audio_channels INTEGER,
                language TEXT, quality REAL, preference REAL, raw_json TEXT,
                captured_at TEXT NOT NULL,
                PRIMARY KEY(site_id, remote_id, asset_id, asset_type)
            );
            CREATE TABLE IF NOT EXISTS thumbnails (
                site_id TEXT NOT NULL, remote_id TEXT NOT NULL, thumb_key TEXT NOT NULL,
                url TEXT, width INTEGER, height INTEGER, preference INTEGER, ext TEXT,
                display_number INTEGER, local_path TEXT, file_size INTEGER,
                selected INTEGER NOT NULL DEFAULT 0, raw_json TEXT,
                captured_at TEXT NOT NULL, downloaded_at TEXT,
                PRIMARY KEY(site_id, remote_id, thumb_key)
            );
            CREATE TABLE IF NOT EXISTS collections (
                source_url TEXT PRIMARY KEY, site_id TEXT NOT NULL, source_type TEXT NOT NULL,
                title TEXT, metadata_json TEXT, item_count INTEGER,
                first_seen_at TEXT NOT NULL, last_scanned_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS collection_items (
                source_url TEXT NOT NULL, site_id TEXT NOT NULL, remote_id TEXT NOT NULL,
                position INTEGER, title TEXT, upload_date TEXT, discovered_at TEXT NOT NULL,
                PRIMARY KEY(source_url, site_id, remote_id)
            );
            CREATE TABLE IF NOT EXISTS download_queue (
                url TEXT PRIMARY KEY, site_id TEXT NOT NULL, remote_id TEXT,
                source_url TEXT, source_type TEXT, status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0, error_message TEXT,
                added_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                started_at TEXT, finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS download_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,
                site_id TEXT NOT NULL, remote_id TEXT, started_at TEXT NOT NULL,
                finished_at TEXT, status TEXT NOT NULL, error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS local_files (
                local_file_id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL,
                remote_id TEXT NOT NULL, file_kind TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
                filename_stem TEXT, container TEXT, video_codec TEXT, audio_codec TEXT,
                width INTEGER, height INTEGER, fps REAL, filesize INTEGER, sha256 TEXT,
                file_exists INTEGER NOT NULL, created_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                site_id TEXT NOT NULL, remote_id TEXT NOT NULL, rating INTEGER,
                favorite INTEGER NOT NULL DEFAULT 0, note TEXT, updated_at TEXT NOT NULL,
                PRIMARY KEY(site_id, remote_id)
            );
            CREATE TABLE IF NOT EXISTS tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT, tag_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS remote_item_tags (
                site_id TEXT NOT NULL, remote_id TEXT NOT NULL, tag_id INTEGER NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(site_id, remote_id, tag_id)
            );
            CREATE INDEX IF NOT EXISTS idx_remote_items_title ON remote_items(title);
            CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue(site_id, status, retry_count);
            CREATE INDEX IF NOT EXISTS idx_local_files_remote ON local_files(site_id, remote_id);
            """
        )
        now = now_iso()
        connection.execute(
            "INSERT INTO database_meta(key,value,updated_at) VALUES('schema_version','1',?) "
            "ON CONFLICT(key) DO UPDATE SET updated_at=excluded.updated_at",
            (now,),
        )
        connection.execute(
            "INSERT INTO sites(site_id,name,base_url,created_at,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(site_id) DO UPDATE SET name=excluded.name,base_url=excluded.base_url,updated_at=excluded.updated_at",
            (site_id, site_name, base_url, now, now),
        )


def _connect() -> sqlite3.Connection:
    if _BASE_DIR is None:
        raise RuntimeError("catalog database is not initialized")
    connection = sqlite3.connect(_BASE_DIR / DB_NAME, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def enqueue_many(site_id: str, items: list[dict]):
    now = now_iso()
    rows = []
    for item in items:
        url = str(item.get("url") or "").strip()
        if url:
            rows.append((url, site_id, item.get("source_url"), source_type(item.get("source_url") or url), now, now))
    if not rows:
        return
    with _connect() as connection:
        connection.executemany(
            "INSERT INTO download_queue(url,site_id,source_url,source_type,status,added_at,updated_at) "
            "VALUES(?,?,?,?,'pending',?,?) ON CONFLICT(url) DO UPDATE SET source_url=COALESCE(excluded.source_url,download_queue.source_url)",
            rows,
        )


def get_resume_urls(site_id: str) -> list[str]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT url FROM download_queue WHERE site_id=? AND "
            "(status IN ('pending','metadata','downloading') OR (status='failed' AND retry_count<?)) "
            "ORDER BY added_at,url",
            (site_id, MAX_RETRIES),
        ).fetchall()
    return [row["url"] for row in rows]


def filter_resume_urls(site_id: str, urls: list[str]) -> list[str]:
    if not urls:
        return []
    with _connect() as connection:
        rows = connection.execute(
            "SELECT url,status FROM download_queue WHERE site_id=? AND url IN (" + ",".join("?" for _ in urls) + ")",
            [site_id, *urls],
        ).fetchall()
    statuses = {row["url"]: row["status"] for row in rows}
    return [url for url in urls if statuses.get(url) not in {"cataloged", "done"}]


def queue_update(url: str, site_id: str, status: str, remote_id: str | None = None, error: str | None = None):
    now = now_iso()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO download_queue(url,site_id,status,added_at,updated_at) VALUES(?,?,?, ?,?) "
            "ON CONFLICT(url) DO NOTHING",
            (url, site_id, status, now, now),
        )
        connection.execute(
            "UPDATE download_queue SET site_id=?,remote_id=COALESCE(?,remote_id),status=?,error_message=?,updated_at=?,"
            "retry_count=CASE WHEN ? IN ('metadata','cataloged','downloading','done') THEN 0 ELSE retry_count END,"
            "started_at=CASE WHEN ?='downloading' THEN COALESCE(started_at,?) ELSE started_at END "
            "WHERE url=?",
            (site_id, remote_id, status, error, now, status, status, now, url),
        )


def queue_failure(url: str, site_id: str, error: Exception, remote_id: str | None = None):
    now = now_iso()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO download_queue(url,site_id,status,added_at,updated_at) VALUES(?,?, 'failed',?,?) "
            "ON CONFLICT(url) DO NOTHING",
            (url, site_id, now, now),
        )
        connection.execute(
            "UPDATE download_queue SET site_id=?,remote_id=COALESCE(?,remote_id),status='failed',"
            "error_message=?,retry_count=retry_count+1,updated_at=? WHERE url=?",
            (site_id, remote_id, str(error)[:4000], now, url),
        )


def save_item(site_id: str, info: dict, source_url: str | None = None):
    remote_id = str(info.get("id") or "")
    if not remote_id:
        return
    now = now_iso()
    creator_key = str(info.get("channel_id") or info.get("uploader_id") or info.get("channel") or info.get("uploader") or "unknown")
    creator_name = info.get("channel") or info.get("uploader") or info.get("creator")
    webpage_url = info.get("webpage_url") or source_url
    canonical_url = webpage_url or f"{info.get('webpage_url_basename') or ''}/{remote_id}"
    with _connect() as connection:
        connection.execute(
            "INSERT INTO creators(site_id,creator_key,name,creator_url,uploader_id,metadata_json,first_seen_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(site_id,creator_key) DO UPDATE SET name=excluded.name,creator_url=excluded.creator_url,"
            "uploader_id=excluded.uploader_id,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at",
            (site_id, creator_key, creator_name, info.get("channel_url") or info.get("uploader_url"), info.get("uploader_id"), json_text(compact_info(info)), now, now),
        )
        connection.execute(
            "INSERT INTO remote_items(site_id,remote_id,canonical_url,webpage_url,title,description,upload_date,timestamp,duration,"
            "creator_key,creator_name,creator_url,uploader_id,age_limit,availability,language,license,tags_json,categories_json,"
            "chapters_json,subtitles_json,automatic_captions_json,metadata_json,first_seen_at,updated_at,metadata_check_count) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(site_id,remote_id) DO UPDATE SET "
            "canonical_url=excluded.canonical_url,webpage_url=excluded.webpage_url,title=excluded.title,description=excluded.description,"
            "upload_date=excluded.upload_date,timestamp=excluded.timestamp,duration=excluded.duration,creator_key=excluded.creator_key,"
            "creator_name=excluded.creator_name,creator_url=excluded.creator_url,uploader_id=excluded.uploader_id,age_limit=excluded.age_limit,"
            "availability=excluded.availability,language=excluded.language,license=excluded.license,tags_json=excluded.tags_json,"
            "categories_json=excluded.categories_json,chapters_json=excluded.chapters_json,subtitles_json=excluded.subtitles_json,"
            "automatic_captions_json=excluded.automatic_captions_json,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at,"
            "metadata_check_count=remote_items.metadata_check_count+1",
            (site_id, remote_id, canonical_url, webpage_url, info.get("title"), info.get("description"), info.get("upload_date"), info.get("timestamp"), info.get("duration"), creator_key, creator_name, info.get("channel_url") or info.get("uploader_url"), info.get("uploader_id"), info.get("age_limit"), info.get("availability"), info.get("language"), info.get("license"), json_text(info.get("tags")), json_text(info.get("categories")), json_text(info.get("chapters")), json_text(info.get("subtitles")), json_text(info.get("automatic_captions")), json_text(compact_info(info)), now, now),
        )
    return remote_id


def _asset_type(fmt: dict) -> str:
    video = (fmt.get("vcodec") or "none") != "none"
    audio = (fmt.get("acodec") or "none") != "none"
    return "muxed" if video and audio else "video" if video else "audio" if audio else "unknown"


def save_streams(site_id: str, info: dict):
    remote_id = str(info.get("id") or "")
    if not remote_id:
        return
    captured = now_iso()
    rows = []
    for fmt in info.get("formats") or []:
        if not fmt.get("format_id"):
            continue
        raw = {key: value for key, value in fmt.items() if key not in {"url", "fragments", "http_headers"}}
        rows.append((site_id, remote_id, str(fmt["format_id"]), _asset_type(fmt), fmt.get("ext"), fmt.get("protocol"), fmt.get("format"), fmt.get("vcodec"), fmt.get("acodec"), fmt.get("width"), fmt.get("height"), fmt.get("fps"), fmt.get("tbr"), fmt.get("vbr"), fmt.get("abr"), fmt.get("asr"), fmt.get("filesize"), fmt.get("filesize_approx"), fmt.get("dynamic_range"), fmt.get("audio_channels"), fmt.get("language"), fmt.get("quality"), fmt.get("preference"), json_text(raw), captured))
    with _connect() as connection:
        connection.executemany(
            "INSERT INTO remote_assets(site_id,remote_id,asset_id,asset_type,ext,protocol,format_name,vcodec,acodec,width,height,fps,tbr,vbr,abr,asr,filesize,filesize_approx,dynamic_range,audio_channels,language,quality,preference,raw_json,captured_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(site_id,remote_id,asset_id,asset_type) DO UPDATE SET "
            "ext=excluded.ext,protocol=excluded.protocol,format_name=excluded.format_name,vcodec=excluded.vcodec,acodec=excluded.acodec,width=excluded.width,height=excluded.height,fps=excluded.fps,tbr=excluded.tbr,vbr=excluded.vbr,abr=excluded.abr,asr=excluded.asr,filesize=excluded.filesize,filesize_approx=excluded.filesize_approx,dynamic_range=excluded.dynamic_range,audio_channels=excluded.audio_channels,language=excluded.language,quality=excluded.quality,preference=excluded.preference,raw_json=excluded.raw_json,captured_at=excluded.captured_at",
            rows,
        )


def save_thumbnails(site_id: str, info: dict, downloaded: list[dict] | None = None):
    remote_id = str(info.get("id") or "")
    if not remote_id:
        return
    downloaded_by_url = {item.get("url"): item for item in (downloaded or []) if item.get("url")}
    captured = now_iso()
    rows = []
    for index, thumb in enumerate(info.get("thumbnails") or [], 1):
        got = downloaded_by_url.get(thumb.get("url"), {})
        path = None
        rows.append((site_id, remote_id, str(thumb.get("id") or thumb.get("preference") or index), thumb.get("url"), thumb.get("width"), thumb.get("height"), thumb.get("preference"), got.get("ext") or thumb.get("ext"), index, None, None, json_text(thumb), captured, None))
    with _connect() as connection:
        connection.executemany(
            "INSERT INTO thumbnails(site_id,remote_id,thumb_key,url,width,height,preference,ext,display_number,local_path,file_size,raw_json,captured_at,downloaded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(site_id,remote_id,thumb_key) DO UPDATE SET url=excluded.url,width=excluded.width,height=excluded.height,preference=excluded.preference,ext=excluded.ext,display_number=excluded.display_number,local_path=NULL,file_size=NULL,raw_json=excluded.raw_json,captured_at=excluded.captured_at,downloaded_at=NULL",
            rows,
        )


def save_collection(site_id: str, source_url: str, info: dict, entries: list[dict]):
    now = now_iso()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO collections(source_url,site_id,source_type,title,metadata_json,item_count,first_seen_at,last_scanned_at) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_url) DO UPDATE SET title=excluded.title,metadata_json=excluded.metadata_json,item_count=excluded.item_count,last_scanned_at=excluded.last_scanned_at",
            (source_url, site_id, source_type(source_url), info.get("title"), json_text(compact_info(info)), len(entries), now, now),
        )
        for position, entry in enumerate(entries, 1):
            remote_id = str(entry.get("id") or "")
            if not remote_id:
                continue
            connection.execute(
                "INSERT INTO collection_items(source_url,site_id,remote_id,position,title,upload_date,discovered_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(source_url,site_id,remote_id) DO UPDATE SET position=excluded.position,title=excluded.title,upload_date=excluded.upload_date,discovered_at=excluded.discovered_at",
                (source_url, site_id, remote_id, position, entry.get("title"), entry.get("upload_date"), now),
            )


def save_local_file(site_id: str, remote_id: str, path: str, info: dict):
    if not path:
        return
    absolute = os.path.abspath(path)
    exists = os.path.isfile(absolute)
    formats = info.get("requested_formats") or info.get("formats") or []
    video = next((fmt for fmt in formats if (fmt.get("vcodec") or "none") != "none"), {})
    audio = next((fmt for fmt in formats if (fmt.get("acodec") or "none") != "none"), {})
    now = now_iso()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO local_files(site_id,remote_id,file_kind,path,filename_stem,container,video_codec,audio_codec,width,height,fps,filesize,file_exists,created_at,last_checked_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET site_id=excluded.site_id,remote_id=excluded.remote_id,file_kind=excluded.file_kind,filename_stem=excluded.filename_stem,container=excluded.container,video_codec=excluded.video_codec,audio_codec=excluded.audio_codec,width=excluded.width,height=excluded.height,fps=excluded.fps,filesize=excluded.filesize,file_exists=excluded.file_exists,last_checked_at=excluded.last_checked_at",
            (site_id, str(remote_id), "video", absolute, Path(absolute).stem, Path(absolute).suffix.lstrip("."), video.get("vcodec"), audio.get("acodec") or video.get("acodec"), video.get("width"), video.get("height"), video.get("fps"), os.path.getsize(absolute) if exists else None, int(exists), now, now),
        )
