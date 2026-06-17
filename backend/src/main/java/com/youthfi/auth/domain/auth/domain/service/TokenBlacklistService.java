package com.youthfi.auth.domain.auth.domain.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Objects;

@Slf4j
@Service
@RequiredArgsConstructor
public class TokenBlacklistService {
    
    private final RedisTemplate<String, String> redisTemplate;
    private final static String blacklistPrefix = "BLACKLIST:";

    // 메서드 이름을 JwtAuthenticationFilter와 동일하게 맞춤
    public boolean isBlacklisted(@NonNull String token) {
        String savedToken = redisTemplate.opsForValue().get(blacklistPrefix + token);
        return savedToken != null && Objects.equals(savedToken, token);
    }

    public void blacklist(@NonNull String token, @NonNull Duration expiration) {
        redisTemplate.opsForValue().set(blacklistPrefix + token, token, expiration);
    }
}