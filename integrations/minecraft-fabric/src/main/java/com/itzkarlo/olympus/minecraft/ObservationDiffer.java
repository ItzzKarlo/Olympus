package com.itzkarlo.olympus.minecraft;

import com.google.gson.JsonObject;
import java.util.ArrayList;
import java.util.List;

final class ObservationDiffer {
    record Facts(
        boolean inSession,
        String connectionType,
        String connectionName,
        String dimension,
        float health,
        float maxHealth
    ) {}

    record Event(String type, JsonObject payload) {}

    private Facts previous;
    private boolean deathReported;

    List<Event> update(Facts current) {
        List<Event> events = new ArrayList<>();
        if (previous == null) {
            previous = current;
            deathReported = current.health() <= 0;
            return events;
        }
        if (!previous.inSession() && current.inSession()) {
            JsonObject payload = new JsonObject();
            payload.addProperty("type", current.connectionType());
            if (current.connectionName() != null) {
                payload.addProperty("name", current.connectionName());
            }
            events.add(new Event("session.joined", payload));
        } else if (previous.inSession() && !current.inSession()) {
            JsonObject payload = new JsonObject();
            payload.addProperty("type", previous.connectionType());
            if (previous.connectionName() != null) {
                payload.addProperty("name", previous.connectionName());
            }
            events.add(new Event("session.left", payload));
        }
        if (previous.inSession() && current.inSession()) {
            if (previous.dimension() != null && current.dimension() != null
                && !previous.dimension().equals(current.dimension())) {
                JsonObject payload = new JsonObject();
                payload.addProperty("from", previous.dimension());
                payload.addProperty("to", current.dimension());
                events.add(new Event("dimension.changed", payload));
            }
            float change = current.health() - previous.health();
            if (change < 0) {
                events.add(new Event("player.damage_taken", healthPayload(-change, current)));
            } else if (change > 0 && previous.health() > 0) {
                events.add(new Event("player.healed", healthPayload(change, current)));
            }
            if (current.health() <= 0 && previous.health() > 0 && !deathReported) {
                events.add(new Event("player.died", new JsonObject()));
                deathReported = true;
            } else if (current.health() > 0) {
                deathReported = false;
            }
        }
        previous = current;
        return events;
    }

    private static JsonObject healthPayload(float amount, Facts current) {
        JsonObject payload = new JsonObject();
        payload.addProperty("amount", amount);
        payload.addProperty("health_after", current.health());
        payload.addProperty("max_health", current.maxHealth());
        return payload;
    }
}
