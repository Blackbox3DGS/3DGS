package com.youthfi.auth.domain.auth.domain.service;

import java.time.Duration;
import java.util.Objects;

import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class TokenWhitelistService {

    private final RedisTemplate<String, String> redisTemplate;

    private static final String WHITELIST_PREFIX = "WHITELIST:";

    public boolean isWhitelistToken(String token) {
        if (token == null) {
            return false;
        }

        String saved = redisTemplate.opsForValue().get(WHITELIST_PREFIX + token);
        return saved != null && Objects.equals(saved, token);
    }

    public void whitelist(String token, Duration timeout) {
        // 🔥 null 방어
        if (token == null || timeout == null) {
            throw new IllegalArgumentException("token 또는 timeout이 null입니다.");
        }

        redisTemplate.opsForValue().set(WHITELIST_PREFIX + token, token, timeout);
    }

    public void deleteWhitelistToken(String token) {
        if (token == null) {
            throw new IllegalArgumentException("token이 null입니다.");
        }

        redisTemplate.delete(WHITELIST_PREFIX + token);
    }
}