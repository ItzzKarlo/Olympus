"""Write development-only News fixtures for end-to-end Olympus testing."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time


PHASES = (
    "ordinary", "duplicate", "developing", "important", "unchanged", "major",
    "cooldown", "multiple", "stale", "recovery",
)

SOURCES = {
    "wire": {"name": "Continental Wire", "language": "en", "trust": 1.0, "region": None, "topic": "transport"},
    "public": {"name": "Public News", "language": "de", "trust": 1.0, "region": "DE", "topic": "transport"},
    "world": {"name": "World Desk", "language": "en", "trust": 1.0, "region": None, "topic": "transport"},
}


def story(guid: str, headline: str, path: str, now: datetime, summary: str | None = None) -> dict[str, object]:
    return {
        "guid": guid,
        "headline": headline,
        "url": f"https://news.example/{path}?utm_source=olympus-fixture",
        "published_at": (now - timedelta(minutes=4)).isoformat(),
        "summary": summary,
        "categories": ["Transport"],
    }


def feed(identifier: str, articles: list[dict[str, object]], *, error: str | None = None) -> dict[str, object]:
    metadata = SOURCES[identifier]
    return {"id": identifier, **metadata, "articles": articles, **({"error": error} if error else {})}


def payload(phase: str, now: datetime) -> dict[str, object]:
    ordinary = story(
        "ordinary-1",
        "European digital standards group concludes scheduled meeting",
        "digital-standards",
        now,
        "The working group published its planned technical recommendations.",
    )
    development = story(
        "rail-wire",
        "Emergency rail disruption affects southern Germany today",
        "rail-disruption-wire",
        now,
        "Operators report widespread cancellations while emergency crews assess the network.",
    )
    confirming = story(
        "rail-public",
        "Emergency rail disruption affects southern Germany today",
        "rail-disruption-public",
        now,
        "Mehrere Betreiber melden umfangreiche Zugausfälle in Süddeutschland.",
    )
    global_confirmation = story(
        "rail-world",
        "Breaking emergency rail disruption affects southern Germany today",
        "rail-disruption-world",
        now,
        "Multiple independent sources now confirm disruption across the regional network.",
    )

    if phase == "stale":
        return {"feeds": [feed(identifier, [], error="Synthetic feed outage") for identifier in SOURCES]}

    feeds = [feed("wire", [ordinary])]
    if phase == "duplicate":
        feeds = [feed("wire", [ordinary, ordinary])]
    if phase in {"developing", "important", "unchanged", "major", "cooldown", "multiple", "recovery"}:
        feeds = [feed("wire", [ordinary, development])]
    if phase in {"important", "unchanged", "major", "cooldown", "multiple", "recovery"}:
        feeds.append(feed("public", [confirming]))
    if phase in {"major", "cooldown", "multiple", "recovery"}:
        feeds.append(feed("world", [global_confirmation]))
    if phase == "multiple":
        simultaneous = [
            "Regional airport closure receives broad independent confirmation",
            "Danube bridge inspection causes widespread freight delays",
            "European ferry operators suspend several coastal routes",
            "Alpine tunnel closure redirects international rail services",
            "Transit workers announce coordinated metropolitan strike",
        ]
        for index, headline in enumerate(simultaneous, start=1):
            for block in feeds:
                block["articles"].append(story(
                    f"simultaneous-{index}-{block['id']}", headline,
                    f"simultaneous-{index}-{block['id']}", now,
                ))
    return {"feeds": feeds}


def write_fixture(path: Path, phase: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload(phase, datetime.now(timezone.utc)), indent=2), encoding="utf-8")
    temporary.replace(path)
    print(f"News fixture → {phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(*PHASES, "sequence"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=5.0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.phase != "sequence":
        write_fixture(args.output, args.phase)
        return
    for phase in PHASES:
        write_fixture(args.output, phase)
        if phase != PHASES[-1]:
            time.sleep(max(0.1, args.delay))


if __name__ == "__main__":
    main()
