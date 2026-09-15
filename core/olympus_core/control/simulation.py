"""Presentation-only fixtures built from normal Olympus models; collectors are untouched."""
from datetime import datetime, timedelta, timezone

from olympus_core.models.state import OlympusState
from .overrides import OverrideDocument, Simulation


def present(real: OlympusState, doc: OverrideDocument) -> OlympusState:
    now = datetime.now(timezone.utc)
    start = datetime.fromtimestamp(doc.created_at, timezone.utc)
    settings = doc.settings
    data = real.model_dump(mode="json")
    data["control"] = {
        "active": True, "seasonal_date": str(settings.seasonal_date) if settings.seasonal_date else None,
        "day_night": settings.day_night, "scene": settings.scene,
        "simulation": settings.simulation.kind if settings.simulation else None,
        "environment": settings.environment.model_dump(), "expires_at": doc.expires_at,
    }
    if settings.day_night != "auto":
        data["time_policy"]["is_night"] = settings.day_night == "night"
        if data["mode"] in {"idle", "night"}:
            data["mode"] = "night" if settings.day_night == "night" else "idle"
    sim = settings.simulation
    if sim is None and settings.scene in {"media", "gaming", "development", "matchday", "news"}:
        sim = Simulation(kind="football" if settings.scene == "matchday" else settings.scene)
    if sim:
        variant = sim.variant
        if sim.kind == "media":
            data["media"] = dict(provider="spotify", available=True, is_playing=variant != "paused", observed_at=start.isoformat(), progress_ms=min(sim.progress, sim.duration) * 1000,
                track=dict(id="control-track", title=sim.title, artists=[dict(name=sim.artist)], duration_ms=sim.duration * 1000, album=dict(name=sim.album)), queue=[])
            data["mode"] = "media"
        elif sim.kind in {"gaming", "development"}:
            game_id = variant if variant and variant != "custom" else "custom"
            names = {"fortnite": "Fortnite", "minecraft": "Minecraft", "among-us": "Among Us", "goat-simulator": "Goat Simulator"}
            game = dict(id=game_id, name=names.get(game_id, sim.title))
            data["machines"]["control-simulation"] = dict(agent_id="control-simulation", hostname=sim.machine, platform="linux", platform_version="simulation", online=True, last_seen=now.isoformat(),
                system=dict(cpu_percent=sim.cpu, ram_percent=sim.ram, ram_used_bytes=int(16 * 1024**3 * sim.ram / 100), ram_total_bytes=16 * 1024**3),
                storage=None, network=None, temperatures=None, gpu=None,
                activity=dict(mode=sim.kind, application=sim.application, process_name=sim.application, game=game if sim.kind == "gaming" else None, fps=sim.fps))
            data["active_device"] = "control-simulation"
            data["mode"] = sim.kind
            if sim.kind == "gaming":
                data["gaming"] = dict(game=game, session_started_at=start.isoformat(), fps=sim.fps)
        elif sim.kind == "news":
            level = variant if variant in {"notable", "important", "major"} else "major"
            source = dict(id="control", name=sim.source, language="en")
            article = dict(id="control", headline=sim.title, source=source, url="https://example.invalid/simulation", canonical_url="https://example.invalid/simulation", observed_at=now.isoformat(), language="en")
            story = dict(id="control", headline=sim.title, summary="SIMULATION — no real news event", language="en", topic="world", articles=[article], sources=[source], first_seen_at=start.isoformat(), latest_seen_at=now.isoformat(), importance=dict(score=.95, level=level))
            data["news"] = dict(available=True, last_updated_at=now.isoformat(), top_stories=[story], ambient=[story], active_story=story,
                presentation=dict(story_id="control", level=level, started_at=start.isoformat(), ends_at=(now + timedelta(hours=1)).isoformat()))
            data["mode"] = "news"
            if variant == "critical":
                data["alerts"].append(alert("critical", sim.title, start, "news"))
        elif sim.kind == "system":
            severity = "warning" if variant in {"warning", "dns-degraded", "agent-offline"} else "critical"
            data["alerts"].append(alert(severity, sim.title if sim.title != "Olympus simulation" else variant.replace("-", " ").title(), start, variant))
            if variant in {"dns-down", "dns-degraded", "gateway-down", "internet-down"}:
                network = data.get("network") or {}
                key = variant.split("-")[0]
                network[key] = {"status": "unknown" if variant == "dns-degraded" else "down", "last_checked": now.isoformat()}
                data["network"] = network
            if variant == "service-down":
                data["services"]["control-simulation"] = dict(id="control-simulation", name="SIMULATED service", status="down")
            if variant == "agent-offline":
                for machine in data["machines"].values():
                    machine["online"] = False
        elif sim.kind == "football":
            home = dict(id="bayern", name="FC Bayern München", short_name="Bayern", code="FCB")
            away = dict(id="dortmund", name="Borussia Dortmund", short_name="Dortmund", code="BVB")
            phase = "pre_match" if variant == "pre-match" else "half_time" if variant == "halftime" else "post_match" if variant in {"full-time", "victory", "defeat", "draw"} else "live"
            score = dict(home=0 if variant == "defeat" else 1, away=0 if variant in {"victory", "bayern-goal"} else 1)
            match = dict(id="control-match", competition=dict(id="control", name="Simulation · Bundesliga"), kickoff=start.isoformat(), home=home, away=away, status=phase, score=score,
                clock=dict(minute=0 if variant == "kickoff" else 46 if variant == "second-half" else 90 if phase == "post_match" else 45 if phase == "half_time" else 28, period="second_half" if variant == "second-half" else "first_half"))
            events = []
            if variant in {"bayern-goal", "opponent-goal"}:
                events = [dict(id="control-goal", type="goal", minute=28, team=home if variant == "bayern-goal" else away, for_tracked_team=variant == "bayern-goal", score_after=score)]
            data["football"] = dict(observed_at=now.isoformat(), tracked_team=home, matchday=dict(active=True, phase=phase, tracked_team=home, match=match, events=events, observed_at=now.isoformat(), result="win" if variant == "victory" else "loss" if variant == "defeat" else "draw" if variant == "draw" else "unknown"))
            data["mode"] = "matchday"
    if settings.scene != "auto":
        data["mode"] = settings.scene
    # Real incidents retain precedence; previews cannot silently suppress them.
    data["alerts"].sort(key=lambda a: (a["source"] == "control-simulation", a["severity"] != "critical"))
    return OlympusState.model_validate(data)


def alert(severity, title, start, kind):
    return dict(id="control-incident", incident_key="control-incident", type=f"control.{kind}", severity=severity,
        title=f"SIMULATION · {title}", message="Temporary Control presentation. Real monitoring continues independently.", source="control-simulation", started_at=start.isoformat(), payload={})
