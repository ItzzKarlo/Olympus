package com.itzkarlo.olympus.minecraft;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

final class IntegrationClient implements AutoCloseable {
    static final int PROTOCOL = 1;
    static final int DEFAULT_PORT = 38_765;
    private static final long RETRY_MILLIS = 2_000;
    private static final int CONNECT_TIMEOUT_MILLIS = 1_500;

    private final BlockingQueue<JsonObject> outbound = new ArrayBlockingQueue<>(128);
    private final AtomicReference<JsonObject> latestState = new AtomicReference<>();
    private final int port;
    private final Thread worker;
    private volatile boolean running = true;

    IntegrationClient() {
        this.port = configuredPort();
        this.worker = Thread.ofPlatform()
            .daemon(true)
            .name("olympus-minecraft-observer")
            .unstarted(this::run);
    }

    void start() {
        worker.start();
    }

    void publishState(JsonObject payload) {
        JsonObject envelope = envelope("state");
        envelope.addProperty("integration", "minecraft");
        envelope.add("payload", payload);
        latestState.set(envelope);
        offer(envelope);
    }

    void publishEvent(String event, JsonObject payload) {
        JsonObject envelope = envelope("event");
        envelope.addProperty("integration", "minecraft");
        envelope.addProperty("event", event);
        envelope.add("payload", payload);
        offer(envelope);
    }

    private void offer(JsonObject message) {
        if (!outbound.offer(message)) {
            outbound.poll();
            outbound.offer(message);
        }
    }

    private void run() {
        while (running) {
            try (Socket socket = new Socket()) {
                socket.connect(
                    new InetSocketAddress(InetAddress.getLoopbackAddress(), port),
                    CONNECT_TIMEOUT_MILLIS
                );
                socket.setTcpNoDelay(true);
                try (
                    BufferedReader reader = new BufferedReader(new InputStreamReader(
                        socket.getInputStream(), StandardCharsets.UTF_8));
                    BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(
                        socket.getOutputStream(), StandardCharsets.UTF_8))
                ) {
                    write(writer, hello());
                    JsonObject welcome = JsonParser.parseString(reader.readLine()).getAsJsonObject();
                    if (welcome.get("protocol").getAsInt() != PROTOCOL
                        || !"welcome".equals(welcome.get("type").getAsString())) {
                        throw new IllegalStateException("Olympus Agent returned an invalid welcome");
                    }
                    JsonObject current = latestState.get();
                    if (current != null) {
                        write(writer, current);
                    }
                    while (running && !socket.isClosed()) {
                        JsonObject message = outbound.poll(1, TimeUnit.SECONDS);
                        if (message != null) {
                            write(writer, message);
                        }
                    }
                }
            } catch (Exception ignored) {
                if (running) {
                    try {
                        Thread.sleep(RETRY_MILLIS);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        }
    }

    private static void write(BufferedWriter writer, JsonObject message) throws Exception {
        writer.write(message.toString());
        writer.newLine();
        writer.flush();
    }

    private static JsonObject hello() {
        JsonObject identity = new JsonObject();
        identity.addProperty("id", "minecraft-fabric");
        identity.addProperty("name", "Minecraft Fabric");
        identity.addProperty("version", OlympusMinecraftClient.VERSION);
        JsonObject message = envelope("hello");
        message.add("integration", identity);
        return message;
    }

    private static JsonObject envelope(String type) {
        JsonObject message = new JsonObject();
        message.addProperty("protocol", PROTOCOL);
        message.addProperty("type", type);
        return message;
    }

    private static int configuredPort() {
        String raw = System.getProperty("olympus.integration.port");
        if (raw == null || raw.isBlank()) {
            raw = System.getenv("OLYMPUS_INTEGRATION_PORT");
        }
        if (raw == null || raw.isBlank()) {
            return DEFAULT_PORT;
        }
        try {
            int value = Integer.parseInt(raw);
            return value >= 1 && value <= 65_535 ? value : DEFAULT_PORT;
        } catch (NumberFormatException ignored) {
            return DEFAULT_PORT;
        }
    }

    @Override
    public void close() {
        running = false;
        worker.interrupt();
    }
}
