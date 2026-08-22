from olympus_agent_common.games import GameProfile


WINDOWS_GAME_PROFILES = (
    GameProfile(
        id="fortnite",
        name="Fortnite",
        process_names=frozenset({"fortniteclient-win64-shipping"}),
    ),
    GameProfile(
        id="among-us",
        name="Among Us",
        process_names=frozenset({"among us"}),
    ),
    GameProfile(
        id="goat-simulator-3",
        name="Goat Simulator 3",
        process_names=frozenset({"goat2-win64-shipping"}),
    ),
    GameProfile(
        id="goat-simulator",
        name="Goat Simulator",
        process_names=frozenset({"goatgame-win64-shipping", "goatgame-win32-shipping"}),
    ),
    GameProfile(
        id="minecraft",
        name="Minecraft",
        process_names=frozenset({"minecraft.windows"}),
    ),
    GameProfile(
        id="minecraft",
        name="Minecraft",
        command_markers=("net.minecraft.client.main.main",),
    ),
    GameProfile(
        id="minecraft",
        name="Minecraft",
        command_markers=("--gamedir", ".minecraft"),
    ),
)
