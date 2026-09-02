from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from pprint import pprint
import csv
import aiohttp
import asyncio
import re


@dataclass
class Package:
    name: str
    repo: str  # owner/repo
    version: str
    version_latest: str | None = None


SCRIPT_DIR = Path(__file__).parent

PACKAGES_CSV_TEMPLATE = SCRIPT_DIR / "packages.csv.template"

STATE_DIR = SCRIPT_DIR / "state"
PACKAGES_CSV = STATE_DIR / "packages.csv"


def load_packages(path: Path) -> list[Package]:
    assert path.exists()
    with open(path, "r") as f:
        return [Package(row[0], row[1], row[2]) for row in csv.reader(f)]


def save_packages(packages: Iterable[Package], path: Path) -> None:
    with open(path, "w") as f:
        writer = csv.writer(f)
        for p in packages:
            writer.writerow([p.name, p.repo, p.version])


async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url) as response:
        return await response.json()


async def fetch_latest_releases(packages: Iterable[Package]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_json(session, f"https://api.github.com/repos/{p.repo}/releases/latest") for p in packages]
        return list(await asyncio.gather(*tasks))


REPO_FROM_RESULT_REGEX = re.compile(f"^.+/repos/(?P<repo>[^/]+/[^/]+)/.+$")
def set_latest_versions(packages: Iterable[Package]) -> None:
    results = asyncio.run(fetch_latest_releases(packages))

    for res in results:
        matched = re.search(REPO_FROM_RESULT_REGEX, res["url"])
        assert matched

        repo = matched.group("repo")
        release_tag = res["tag_name"]

        pkg = next(filter(lambda p: p.repo == repo, packages))
        pkg.version_latest = release_tag

    assert all([p.version_latest for p in packages])


def main() -> None:
    assert PACKAGES_CSV_TEMPLATE.exists()

    if not STATE_DIR.exists():
        STATE_DIR.mkdir()
    if not PACKAGES_CSV.exists():
        PACKAGES_CSV_TEMPLATE.copy(PACKAGES_CSV)

    packages = load_packages(PACKAGES_CSV)
    set_latest_versions(packages)

    packages_to_build = list(filter(lambda p: p.version != p.version_latest, packages))

    save_packages(packages, PACKAGES_CSV)
    pprint(packages)

if __name__ == "__main__":
    main()
