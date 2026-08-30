from __future__ import annotations

import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class SiteConfig:
    site_id: str
    site_name: str
    folder_name: str
    base_url: str
    domains: tuple[str, ...]
    default_format: str | None = None
    default_container: str = "mkv"


YOUTUBE_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]/"
    "best[ext=mp4][vcodec^=avc1][acodec^=mp4a]/"
    "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best"
)


SITE_CONFIGS = (
    SiteConfig("youtube", "YouTube", "YouTube", "https://www.youtube.com", ("youtube.com", "youtu.be"), YOUTUBE_FORMAT, "mp4"),
    SiteConfig("iwara", "iwara", "iwara", "https://www.iwara.tv", ("iwara.tv",)),
    SiteConfig("pornhub", "PornHub", "PornHub", "https://www.pornhub.com", ("pornhub.com",)),
    SiteConfig("xnxx", "XNXX", "XNXX", "https://www.xnxx.com", ("xnxx.com",)),
    SiteConfig("xvideos", "Xvideos", "Xvideos", "https://www.xvideos.com", ("xvideos.com",)),
)


def normalize_url(value: str) -> str:
    value = value.strip().strip("`").strip()
    if value.startswith("[") and "](" in value and value.endswith(")"):
        value = value[value.find("](") + 2:-1]
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    return value


def site_for_url(url: str) -> SiteConfig | None:
    host = (urllib.parse.urlparse(url).hostname or "").lower().strip(".")
    for config in SITE_CONFIGS:
        if any(host == domain or host.endswith("." + domain) for domain in config.domains):
            return config
    return None


def group_urls(urls: list[str]) -> dict[SiteConfig, list[str]]:
    grouped: dict[SiteConfig, list[str]] = {}
    for raw_url in urls:
        url = normalize_url(raw_url)
        if not url:
            continue
        config = site_for_url(url)
        if config is None:
            raise ValueError(f"対応サイト外のURLです: {url}")
        grouped.setdefault(config, []).append(url)
    return grouped
