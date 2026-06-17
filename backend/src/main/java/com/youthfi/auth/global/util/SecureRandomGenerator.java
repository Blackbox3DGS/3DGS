package com.youthfi.auth.global.util;

import org.springframework.stereotype.Component;

import java.security.SecureRandom;

@Component
public class SecureRandomGenerator {

    private final SecureRandom secureRandom = new SecureRandom();

    public String generate() {
        int random = secureRandom.nextInt(1_000_000);
        return String.format("%06d", random);
    }

}


