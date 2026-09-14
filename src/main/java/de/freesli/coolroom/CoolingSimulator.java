package de.freesli.coolroom;

import java.time.Instant;
import java.util.concurrent.ThreadLocalRandom;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class CoolingSimulator {

    private static final Logger log =
            LoggerFactory.getLogger(CoolingSimulator.class);

    private final MeasurementRepository repository;

    private double temperatureFront = 8.0;
    private double temperatureRear = 8.5;

    private boolean cooling = false;

    public CoolingSimulator(MeasurementRepository repository) {
        this.repository = repository;
    }

    @Scheduled(fixedDelay = 5000)
    public void simulate() {
        // Die bisherige Kühlstellung beeinflusst die Temperaturen.
        temperatureFront = nextTemperature(temperatureFront);
        temperatureRear = nextTemperature(temperatureRear);

        // Für die Regelung zählt die wärmere Messstelle.
        double highestTemperature =
                Math.max(temperatureFront, temperatureRear);

        if (highestTemperature > 10.0) {
            cooling = true;
        } else if (highestTemperature <= 8.0) {
            cooling = false;
        }
        // Zwischen 8 und 10 °C bleibt der bisherige Zustand erhalten.

        int fanPercent = cooling ? 100 : 0;
        int valvePercent = cooling ? 100 : 0;

        Instant timestamp = Instant.now();

        repository.save(new Measurement(
                null,
                "Sensor vorne",
                timestamp,
                temperatureFront
        ));

        repository.save(new Measurement(
                null,
                "Sensor hinten",
                timestamp,
                temperatureRear
        ));

        log.info(
                "Vorne: {} °C | Hinten: {} °C | Lüfter: {} % | Ventil: {} %",
                temperatureFront,
                temperatureRear,
                fanPercent,
                valvePercent
        );
    }

    private double nextTemperature(double currentTemperature) {
        double change = cooling ? -0.3 : 0.2;

        // Kleine zufällige Schwankung pro Messung.
        double noise = ThreadLocalRandom.current()
                .nextDouble(-0.05, 0.05);

        double next = currentTemperature + change + noise;

        return Math.round(next * 100.0) / 100.0;
    }
}
