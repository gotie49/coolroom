package de.freesli.coolroom;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class CoolroomApplication {

	public static void main(String[] args) {
		SpringApplication.run(CoolroomApplication.class, args);
	}

}
