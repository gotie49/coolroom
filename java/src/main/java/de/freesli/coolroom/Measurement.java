package de.freesli.coolroom;

import java.time.Instant;

public record Measurement(
        Long id,
        String sensorName,
        Instant timestamp,
        double temperature
) {}
