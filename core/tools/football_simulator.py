"""Write development-only API-Football fixtures for end-to-end Matchday testing."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time


PHASES = ("upcoming", "pre_match", "live", "goal", "yellow", "half_time", "second_half", "opponent_goal", "bayern_goal", "full_time", "outage")


def event(minute: int, team: int, player: str, kind: str, detail: str, assist: str | None = None) -> dict[str, object]:
    return {
        "time": {"elapsed": minute, "extra": None},
        "team": {"id": team, "name": "Bayern Munich" if team == 157 else "Borussia Dortmund"},
        "player": {"id": f"{team}-{player}", "name": player},
        "assist": {"id": f"assist-{assist}", "name": assist} if assist else {"id": None, "name": None},
        "type": kind,
        "detail": detail,
    }


def payload(phase: str, now: datetime) -> dict[str, object]:
    if phase == "outage":
        return {"response": []}
    kickoff = now + timedelta(days=1)
    status = "NS"
    elapsed = None
    score = (None, None)
    events: list[dict[str, object]] = []
    if phase == "pre_match":
        kickoff = now + timedelta(minutes=30)
    elif phase in {"live", "goal", "yellow"}:
        kickoff = now - timedelta(minutes=28)
        status = "1H"
        elapsed = 28
        if phase in {"goal", "yellow"}:
            events.append(event(17, 157, "Harry Kane", "Goal", "Normal Goal", "Jamal Musiala"))
            score = (1, 0)
        if phase == "yellow":
            events.append(event(26, 165, "Opponent Defender", "Card", "Yellow Card"))
    elif phase == "half_time":
        kickoff = now - timedelta(minutes=52)
        status = "HT"
        elapsed = 45
        events.append(event(17, 157, "Harry Kane", "Goal", "Normal Goal", "Jamal Musiala"))
        score = (1, 0)
    elif phase in {"second_half", "opponent_goal", "bayern_goal"}:
        kickoff = now - timedelta(minutes=76)
        status = "2H"
        elapsed = 63
        events.append(event(17, 157, "Harry Kane", "Goal", "Normal Goal", "Jamal Musiala"))
        score = (1, 0)
        if phase in {"opponent_goal", "bayern_goal"}:
            events.append(event(58, 165, "Opponent Forward", "Goal", "Normal Goal"))
            score = (1, 1)
        if phase == "bayern_goal":
            events.append(event(62, 157, "Jamal Musiala", "Goal", "Normal Goal", "Joshua Kimmich"))
            score = (2, 1)
    elif phase == "full_time":
        kickoff = now - timedelta(hours=2)
        status = "FT"
        elapsed = 90
        events = [
            event(17, 157, "Harry Kane", "Goal", "Normal Goal", "Jamal Musiala"),
            event(58, 165, "Opponent Forward", "Goal", "Normal Goal"),
            event(62, 157, "Jamal Musiala", "Goal", "Normal Goal", "Joshua Kimmich"),
        ]
        score = (2, 1)

    fixture = {
        "fixture": {
            "id": 99009,
            "date": kickoff.isoformat(),
            "venue": {"name": "Allianz Arena"},
            "status": {"short": status, "elapsed": elapsed, "extra": None},
        },
        "league": {"id": 78, "name": "Bundesliga"},
        "teams": {
            "home": {"id": 157, "name": "Bayern Munich", "code": "BAY"},
            "away": {"id": 165, "name": "Borussia Dortmund", "code": "BVB"},
        },
        "goals": {"home": score[0], "away": score[1]},
        "events": events,
        "lineups": [
            {
                "team": {"id": 157, "name": "Bayern Munich"},
                "formation": "4-2-3-1",
                "startXI": [
                    {"player": {"id": index, "name": name, "number": number, "pos": position}}
                    for index, (name, number, position) in enumerate([
                        ("Manuel Neuer", 1, "G"), ("Konrad Laimer", 27, "D"), ("Dayot Upamecano", 2, "D"),
                        ("Jonathan Tah", 4, "D"), ("Alphonso Davies", 19, "D"), ("Joshua Kimmich", 6, "M"),
                        ("Aleksandar Pavlović", 45, "M"), ("Michael Olise", 17, "M"), ("Jamal Musiala", 10, "M"),
                        ("Luis Díaz", 14, "M"), ("Harry Kane", 9, "F"),
                    ], start=1)
                ],
                "substitutes": [],
            },
            {
                "team": {"id": 165, "name": "Borussia Dortmund"},
                "formation": "3-4-2-1",
                "startXI": [],
                "substitutes": [],
            },
        ] if phase != "upcoming" else [],
        "statistics": [
            {"team": {"id": 157, "name": "Bayern Munich"}, "statistics": [
                {"type": "Ball Possession", "value": "61%"}, {"type": "Total Shots", "value": 14},
                {"type": "Shots on Goal", "value": 7}, {"type": "Corner Kicks", "value": 6},
            ]},
            {"team": {"id": 165, "name": "Borussia Dortmund"}, "statistics": [
                {"type": "Ball Possession", "value": "39%"}, {"type": "Total Shots", "value": 6},
                {"type": "Shots on Goal", "value": 2}, {"type": "Corner Kicks", "value": 3},
            ]},
        ] if status != "NS" else [],
    }
    return {"response": [fixture]}


def write_fixture(path: Path, phase: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload(phase, datetime.now(timezone.utc)), indent=2), encoding="utf-8")
    temporary.replace(path)
    print(f"Matchday fixture → {phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(*PHASES, "sequence"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=16.0, help="Seconds between sequence phases")
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
