package com.itzkarlo.olympus.minecraft;

import com.google.gson.JsonObject;
import java.util.Locale;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.resources.Identifier;

public final class OlympusMinecraftClient implements ClientModInitializer {
    static final String VERSION = "0.1.0";
    private static final int SAMPLE_TICKS = 5;

    private final IntegrationClient integration = new IntegrationClient();
    private final ObservationDiffer differ = new ObservationDiffer();
    private int ticks;
    private String previousState;

    @Override
    public void onInitializeClient() {
        integration.start();
        ClientTickEvents.END_CLIENT_TICK.register(this::tick);
    }

    private void tick(Minecraft client) {
        ticks++;
        if (ticks % SAMPLE_TICKS != 0) {
            return;
        }
        LocalPlayer player = client.player;
        boolean inSession = player != null && client.level != null;
        String connectionType = connectionType(client);
        String connectionName = connectionName(client);
        String dimension = inSession ? dimension(client) : null;
        float health = inSession ? player.getHealth() : 0;
        float maxHealth = inSession ? player.getMaxHealth() : 0;
        ObservationDiffer.Facts facts = new ObservationDiffer.Facts(
            inSession,
            connectionType,
            connectionName,
            dimension,
            health,
            maxHealth
        );
        for (ObservationDiffer.Event event : differ.update(facts)) {
            integration.publishEvent(event.type(), event.payload());
        }
        if (!inSession) {
            if (previousState != null) {
                integration.clearState();
            }
            previousState = null;
            return;
        }
        JsonObject state = state(client, player, connectionType, connectionName, dimension);
        String serialized = state.toString();
        if (!serialized.equals(previousState)) {
            integration.publishState(state);
            previousState = serialized;
        }
    }

    private static JsonObject state(
        Minecraft client,
        LocalPlayer player,
        String connectionType,
        String connectionName,
        String dimension
    ) {
        JsonObject connection = new JsonObject();
        connection.addProperty("type", connectionType);
        if ("multiplayer".equals(connectionType)) {
            ServerData server = client.getCurrentServer();
            if (server != null) {
                connection.addProperty("server_name", server.name);
                connection.addProperty("server_address", server.ip);
            }
        } else if (connectionName != null) {
            connection.addProperty("world_name", connectionName);
        }

        JsonObject world = new JsonObject();
        world.addProperty("dimension", dimension);
        Identifier biome = client.level.getBiome(player.blockPosition())
            .unwrapKey()
            .map(key -> key.identifier())
            .orElse(null);
        world.addProperty("biome", biome == null ? "unknown" : normalizeId(biome.toString()));

        JsonObject position = new JsonObject();
        position.addProperty("x", player.getX());
        position.addProperty("y", player.getY());
        position.addProperty("z", player.getZ());

        JsonObject experience = new JsonObject();
        experience.addProperty("level", player.experienceLevel);
        experience.addProperty("progress", player.experienceProgress);

        JsonObject playerState = new JsonObject();
        playerState.add("position", position);
        playerState.addProperty("health", player.getHealth());
        playerState.addProperty("max_health", player.getMaxHealth());
        playerState.addProperty("food", player.getFoodData().getFoodLevel());
        playerState.addProperty("max_food", 20);
        playerState.addProperty("armor", player.getArmorValue());
        playerState.add("experience", experience);
        playerState.addProperty("game_mode", gameMode(client));

        JsonObject state = new JsonObject();
        state.add("connection", connection);
        state.add("world", world);
        state.add("player", playerState);
        return state;
    }

    private static String connectionType(Minecraft client) {
        return client.hasSingleplayerServer() ? "singleplayer" : "multiplayer";
    }

    private static String connectionName(Minecraft client) {
        if (client.hasSingleplayerServer() && client.getSingleplayerServer() != null) {
            return client.getSingleplayerServer().getWorldData().getLevelName();
        }
        ServerData server = client.getCurrentServer();
        return server == null ? null : server.name;
    }

    private static String dimension(Minecraft client) {
        return normalizeId(client.level.dimension().identifier().toString());
    }

    private static String gameMode(Minecraft client) {
        if (client.gameMode == null) {
            return "unknown";
        }
        String value = client.gameMode.getPlayerMode().getName().toLowerCase(Locale.ROOT);
        return switch (value) {
            case "survival", "creative", "adventure", "spectator" -> value;
            default -> "unknown";
        };
    }

    private static String normalizeId(String id) {
        return id.startsWith("minecraft:") ? id.substring("minecraft:".length()) : id;
    }
}
