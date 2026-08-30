from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from url_router import SITE_CONFIGS, group_urls


ROOT = Path(__file__).resolve().parent.parent


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SITE_Source 共通URL受付")
    parser.add_argument("urls", nargs="*", help="動画または一覧URL")
    parser.add_argument("-f", "--url-file", action="append", default=[], help="URL一覧ファイル")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--skip-thumbnails", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--expected-owner")
    parser.add_argument("--cookies-from-browser", "--browser", dest="browser")
    parser.add_argument("--cookies")
    parser.add_argument("--format")
    parser.add_argument("-o", "--output-dir")
    parser.add_argument("--workers", type=int, default=6)
    return parser


def site_argv(urls: list[str], args: argparse.Namespace) -> list[str]:
    forwarded = list(urls)
    for flag, enabled in (("--metadata-only", args.metadata_only), ("--skip-thumbnails", args.skip_thumbnails), ("--resume", args.resume)):
        if enabled:
            forwarded.append(flag)
    if args.expected_owner:
        forwarded.extend(("--expected-owner", args.expected_owner))
    if args.browser:
        forwarded.extend(("--cookies-from-browser", args.browser))
    if args.cookies:
        forwarded.extend(("--cookies", args.cookies))
    if args.format:
        forwarded.extend(("--format", args.format))
    if args.output_dir:
        forwarded.extend(("--output-dir", args.output_dir))
    if args.workers != 6:
        forwarded.extend(("--workers", str(args.workers)))
    return forwarded


def run_site(config, urls: list[str], args: argparse.Namespace) -> int:
    site_root = ROOT / "SITES" / config.folder_name
    program = site_root / f"{config.folder_name}_downloader" / "downloader.py"
    if not program.is_file():
        print(f"サイトプログラムがありません: {program}")
        return 1
    environment = os.environ.copy()
    environment["SITE_SOURCE_SITE_ROOT"] = str(site_root)
    command = [sys.executable, str(program), *site_argv(urls, args)]
    return subprocess.run(command, cwd=program.parent, env=environment).returncode


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cookies and args.browser:
        build_parser().error("--cookies と --cookies-from-browser は同時指定できません")
    if args.workers < 1:
        build_parser().error("--workers は1以上で指定してください")
    interactive = argv is None and len(sys.argv) == 1

    while True:
        urls = list(args.urls)
        for filename in args.url_file:
            urls.extend(read_urls([filename]))
        if not urls and not args.resume:
            urls = prompt_urls()
        grouped = group_urls(urls) if urls else {}
        if args.resume:
            for config in SITE_CONFIGS:
                grouped.setdefault(config, [])
        if not grouped:
            print("URLがないため終了します")
            return 0

        status = 0
        for config, config_urls in grouped.items():
            status |= run_site(config, config_urls, args)
        if not interactive:
            return status
        print("\n処理が完了しました。次のURLを入力できます。終了する場合は空行でEnterを押してください。")


if __name__ == "__main__":
    raise SystemExit(main())
