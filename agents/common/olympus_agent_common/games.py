from dataclasses import dataclass
import time
from typing import Callable, Iterable

from olympus_agent_common.activity import normalize_process_name
from olympus_agent_common.protocol import ActivityObservation, GameObservation


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    pid: int
    name: str
    cmdline: tuple[str, ...] = ()

    @property
    def normalized_name(self) -> str:
        return normalize_process_name(self.name)


@dataclass(frozen=True, slots=True)
class GameProfile:
    id: str
    name: str
    process_names: frozenset[str] = frozenset()
    command_markers: tuple[str, ...] = ()

    def matches(self, process: ProcessInfo) -> bool:
        if process.normalized_name in self.process_names:
            return True
        command = " ".join(process.cmdline).casefold()
        return bool(self.command_markers) and all(
            marker.casefold() in command for marker in self.command_markers
        )


@dataclass(frozen=True, slots=True)
class GameProcess:
    profile: GameProfile
    process: ProcessInfo


def find_game_processes(
    processes: Iterable[ProcessInfo],
    profiles: Iterable[GameProfile],
) -> list[GameProcess]:
    matches: list[GameProcess] = []
    for process in processes:
        for profile in profiles:
            if profile.matches(process):
                matches.append(GameProcess(profile, process))
                break
    return matches


class ForegroundGameDetector:
    def __init__(
        self,
        profiles: tuple[GameProfile, ...],
        grace_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._profiles = profiles
        self._grace_seconds = grace_seconds
        self._clock = clock
        self._last_foreground_at: float | None = None
        self._active: GameProcess | None = None

    def detect(
        self,
        processes: Iterable[ProcessInfo],
        foreground_pid: int | None,
        fps: float | None = None,
    ) -> ActivityObservation | None:
        now = self._clock()
        matches = find_game_processes(processes, self._profiles)
        foreground = next(
            (match for match in matches if match.process.pid == foreground_pid),
            None,
        )
        if foreground is not None:
            self._active = foreground
            self._last_foreground_at = now
        elif self._active is not None:
            still_running = next(
                (
                    match
                    for match in matches
                    if match.process.pid == self._active.process.pid
                    and match.profile.id == self._active.profile.id
                ),
                None,
            )
            within_grace = (
                self._last_foreground_at is not None
                and now - self._last_foreground_at <= self._grace_seconds
            )
            self._active = still_running if still_running and within_grace else None

        if self._active is None:
            self._last_foreground_at = None
            return None
        game = GameObservation(self._active.profile.id, self._active.profile.name)
        return ActivityObservation(
            mode="gaming",
            application=game.name,
            process_name=self._active.process.name,
            game=game,
            fps=fps,
        )


def detect_running_game(
    processes: Iterable[ProcessInfo],
    profiles: tuple[GameProfile, ...],
) -> ActivityObservation | None:
    match = next(iter(find_game_processes(processes, profiles)), None)
    if match is None:
        return None
    game = GameObservation(match.profile.id, match.profile.name)
    return ActivityObservation(
        mode="gaming",
        application=game.name,
        process_name=match.process.name,
        game=game,
    )
