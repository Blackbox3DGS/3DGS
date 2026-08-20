package com.youthfi.auth.domain.auth.domain.service;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Objects;

@Service
@RequiredArgsConstructor
public class RefreshTokenService {

    private static final String REFRESH_TOKEN_PREFIX = "REFRESH_TOKEN:";
    private final RedisTemplate<String, String> redisTemplate;

    public void saveRefreshToken(String userId, String refreshToken, Duration timeout) {
        // null 방어 코드
        if (userId == null || refreshToken == null || timeout == null) {
            throw new IllegalArgumentException("RefreshToken 저장 값이 null입니다.");
        }

        redisTemplate.opsForValue().set(REFRESH_TOKEN_PREFIX + userId, refreshToken, timeout);
    }

    public void deleteRefreshToken(String userId) {
        if (userId == null) {
            throw new IllegalArgumentException("userId가 null입니다.");
        }

        redisTemplate.delete(REFRESH_TOKEN_PREFIX + userId);
    }

    public String findByUserId(String userId) {
        if (userId == null) {
            throw new IllegalArgumentException("userId가 null입니다.");
        }

        return redisTemplate.opsForValue().get(REFRESH_TOKEN_PREFIX + userId);
    }

    public boolean isExist(String token, String userId) {
        if (token == null || userId == null) {
            return false;
        }

        String savedToken = redisTemplate.opsForValue().get(REFRESH_TOKEN_PREFIX + userId);
        return savedToken != null && Objects.equals(savedToken, token);
    }
}