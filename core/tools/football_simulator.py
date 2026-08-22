"""Write development-only API-Football fixtures for end-to-end Matchday testing."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time


PHASES = (
    "upcoming", "pre_match", "live", "ratings", "goal", "stats_30", "half_time",
    "second_half", "substitution", "opponent_goal", "red", "bayern_goal",
    "full_time", "loss", "missing_players", "low_quota", "outage",
)

BAYERN = [
    (8, "Manuel Neuer", 1, "G"), (9, "Konrad Laimer", 27, "D"),
    (10, "Dayot Upamecano", 2, "D"), (11, "Jonathan Tah", 4, "D"),
    (12, "Alphonso Davies", 19, "D"), (3, "Joshua Kimmich", 6, "M"),
    (13, "Aleksandar Pavlović", 45, "M"), (4, "Michael Olise", 17, "M"),
    (2, "Jamal Musiala", 10, "M"), (14, "Luis Díaz", 14, "M"),
    (1, "Harry Kane", 9, "F"),
]
DORTMUND = [
    (101, "Gregor Kobel", 1, "G"), (102, "Waldemar Anton", 3, "D"),
    (103, "Nico Schlotterbeck", 4, "D"), (104, "Ramy Bensebaini", 5, "D"),
    (105, "Julian Ryerson", 26, "M"), (106, "Felix Nmecha", 8, "M"),
    (107, "Marcel Sabitzer", 20, "M"), (108, "Daniel Svensson", 24, "M"),
    (109, "Karim Adeyemi", 27, "F"), (110, "Julian Brandt", 10, "F"),
    (111, "Serhou Guirassy", 9, "F"),
]


def event(minute: int, team: int, player_id: int, player: str, kind: str, detail: str,
          assist_id: int | None = None, assist: str | None = None) -> dict[str, object]:
    return {
        "time": {"elapsed": minute, "extra": None},
        "team": {"id": team, "name": "Bayern Munich" if team == 157 else "Borussia Dortmund"},
        "player": {"id": player_id, "name": player},
        "assist": {"id": assist_id, "name": assist} if assist else {"id": None, "name": None},
        "type": kind, "detail": detail,
    }


def lineup(team: int, players: list[tuple[int, str, int, str]], formation: str) -> dict[str, object]:
    return {
        "team": {"id": team, "name": "Bayern Munich" if team == 157 else "Borussia Dortmund"},
        "formation": formation,
        "startXI": [{"player": {"id": identifier, "name": name, "number": number, "pos": position}}
                    for identifier, name, number, position in players],
        "substitutes": [],
    }


def team_statistics(team: int, possession: int, shots: int, on_target: int, corners: int,
                    passes: int, accuracy: int, fouls: int, yellow: int = 0, red: int = 0) -> dict[str, object]:
    return {
        "team": {"id": team, "name": "Bayern Munich" if team == 157 else "Borussia Dortmund"},
        "statistics": [
            {"type": "Ball Possession", "value": f"{possession}%"},
            {"type": "Total Shots", "value": shots}, {"type": "Shots on Goal", "value": on_target},
            {"type": "Corner Kicks", "value": corners}, {"type": "Total passes", "value": passes},
            {"type": "Passes %", "value": f"{accuracy}%"}, {"type": "Fouls", "value": fouls},
            {"type": "Yellow Cards", "value": yellow}, {"type": "Red Cards", "value": red},
        ],
    }


def player_stat(identifier: int, name: str, number: int, position: str, rating: float | None,
                minutes: int, *, goals: int = 0, assists: int = 0, shots: int = 0,
                on_target: int = 0, key_passes: int = 0, duels: int = 0,
                duels_won: int = 0, substitute: bool = False) -> dict[str, object]:
    return {
        "player": {"id": identifier, "name": name},
        "statistics": [{
            "games": {"minutes": minutes, "number": number, "position": position,
                      "rating": None if rating is None else f"{rating:.1f}", "substitute": substitute},
            "shots": {"total": shots, "on": on_target}, "goals": {"total": goals, "assists": assists},
            "passes": {"total": max(5, minutes // 2), "key": key_passes, "accuracy": "87%"},
            "tackles": {"total": 1, "interceptions": 1, "blocks": 0},
            "duels": {"total": duels, "won": duels_won}, "dribbles": {"attempts": 2, "success": 1},
            "fouls": {"committed": 1, "drawn": 1}, "cards": {"yellow": 0, "red": 0},
            "penalty": {"won": 0, "committed": 0, "scored": 0, "missed": 0, "saved": 0},
        }],
    }


def player_blocks(minute: int, score: tuple[int | None, int | None], phase: str) -> list[dict[str, object]]:
    if phase == "missing_players":
        return [{"team": {"id": 165, "name": "Borussia Dortmund"}, "players": []}]
    first_goal = score[0] is not None and score[0] >= 1
    second_goal = phase in {"bayern_goal", "full_time"}
    opponent_goal = score[1] is not None and score[1] >= 1
    kane_rating = 7.0 if phase == "live" else 7.3 if phase == "ratings" else 8.1 if first_goal else 7.1
    return [
        {"team": {"id": 157, "name": "Bayern Munich"}, "players": [
            player_stat(1, "Harry Kane", 9, "F", kane_rating, minute, goals=1 if first_goal else 0,
                        shots=4 if first_goal else 2, on_target=2 if first_goal else 1, duels=6, duels_won=4),
            player_stat(2, "Jamal Musiala", 10, "M", 8.7 if second_goal else 7.1, minute,
                        goals=1 if second_goal else 0, assists=1 if first_goal else 0,
                        shots=3, on_target=2, key_passes=3, duels=9, duels_won=6),
            player_stat(3, "Joshua Kimmich", 6, "M", 7.4 if minute >= 45 else 7.0, minute,
                        assists=1 if second_goal else 0, key_passes=4, duels=7, duels_won=5),
            player_stat(4, "Michael Olise", 17, "M", 7.5, minute, shots=2, on_target=1, key_passes=2),
        ]},
        {"team": {"id": 165, "name": "Borussia Dortmund"}, "players": [
            player_stat(111, "Serhou Guirassy", 9, "F", 7.8 if opponent_goal else 6.8, minute,
                        goals=1 if opponent_goal else 0, shots=3, on_target=2),
            player_stat(110, "Julian Brandt", 10, "F", 7.3, minute, key_passes=2),
            player_stat(101, "Gregor Kobel", 1, "G", 7.2, minute),
        ]},
    ]


def phase_state(phase: str, now: datetime) -> tuple[datetime, str, int | None, tuple[int | None, int | None], list[dict[str, object]]]:
    kickoff, status, minute, score = now + timedelta(days=1), "NS", None, (None, None)
    events: list[dict[str, object]] = []
    if phase in {"pre_match", "missing_players"}:
        kickoff = now + timedelta(minutes=30)
    if phase not in {"upcoming", "pre_match", "missing_players", "outage"}:
        minutes = {"live": 12, "ratings": 16, "goal": 23, "stats_30": 30, "half_time": 45,
                   "second_half": 52, "substitution": 61, "opponent_goal": 68, "red": 74,
                   "bayern_goal": 83, "full_time": 90, "loss": 90, "low_quota": 76}
        minute = minutes[phase]
        kickoff = now - timedelta(minutes=minute)
        status = "HT" if phase == "half_time" else "FT" if phase in {"full_time", "loss"} else "1H" if minute < 45 else "2H"
        score = (0, 0)
        if phase in {"goal", "stats_30", "half_time", "second_half", "substitution", "opponent_goal", "red", "bayern_goal", "full_time", "low_quota"}:
            events.append(event(23, 157, 1, "Harry Kane", "Goal", "Normal Goal", 2, "Jamal Musiala"))
            score = (1, 0)
        if phase in {"substitution", "opponent_goal", "red", "bayern_goal", "full_time", "low_quota"}:
            events.append(event(61, 157, 1, "Harry Kane", "subst", "Substitution 1", 15, "Thomas Müller"))
        if phase in {"opponent_goal", "red", "bayern_goal", "full_time", "low_quota"}:
            events.append(event(68, 165, 111, "Serhou Guirassy", "Goal", "Normal Goal", 110, "Julian Brandt"))
            score = (1, 1)
        if phase in {"red", "bayern_goal", "full_time", "low_quota"}:
            events.append(event(74, 165, 103, "Nico Schlotterbeck", "Card", "Red Card"))
        if phase in {"bayern_goal", "full_time"}:
            events.append(event(83, 157, 2, "Jamal Musiala", "Goal", "Normal Goal", 3, "Joshua Kimmich"))
            score = (2, 1)
        if phase == "loss":
            events = [event(37, 165, 111, "Serhou Guirassy", "Goal", "Normal Goal")]
            score = (0, 1)
    return kickoff, status, minute, score, events


def payload(phase: str, now: datetime) -> dict[str, object]:
    if phase == "outage":
        return {"response": []}
    kickoff, status, minute, score, events = phase_state(phase, now)
    live_data = status != "NS"
    home_stats = (61, 14, 7, 6, 520, 89, 8) if (minute or 0) >= 75 else (58, 8, 4, 4, 286, 87, 5)
    away_stats = (39, 7, 3, 3, 314, 84, 11) if (minute or 0) >= 75 else (42, 4, 1, 2, 205, 83, 7)
    fixture = {
        "fixture": {"id": 99009, "date": kickoff.isoformat(), "venue": {"name": "Allianz Arena"},
                    "status": {"short": status, "elapsed": minute, "extra": None}},
        "league": {"id": 78, "name": "Bundesliga"},
        "teams": {"home": {"id": 157, "name": "Bayern Munich", "code": "BAY"},
                  "away": {"id": 165, "name": "Borussia Dortmund", "code": "BVB"}},
        "goals": {"home": score[0], "away": score[1]}, "events": events,
        "lineups": [] if phase in {"upcoming", "missing_players"} else [
            lineup(157, BAYERN, "4-2-3-1"), lineup(165, DORTMUND, "3-4-2-1")],
        "statistics": [team_statistics(157, *home_stats), team_statistics(165, *away_stats)] if live_data else [],
        "players": player_blocks(minute or 0, score, phase) if live_data else [],
    }
    result: dict[str, object] = {"response": [fixture]}
    if phase == "low_quota":
        result["olympus_quota"] = {"daily_limit": 100, "daily_remaining": 4, "minute_limit": 10, "minute_remaining": 6}
    return result


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
