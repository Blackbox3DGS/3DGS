package com.youthfi.auth.domain.email.domain.service;

import java.time.Duration;
import java.util.Objects;
import java.util.Random;

import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class EmailVerificationService {

    private final RedisTemplate<String, String> redisTemplate;

    private static final String VERIFICATION_PREFIX = "EMAIL_VERIFIED:";
    private static final String VERIFICATION_CODE_PREFIX = "EMAIL_VERIFICATION_CODE:";
    private static final String VERIFICATION_ATTEMPT_PREFIX = "EMAIL_VERIFICATION_ATTEMPT:";

    private static final long VERIFICATION_CODE_TTL_SECONDS = 300;
    private static final int MAX_ATTEMPT_COUNT = 5;
    private static final long ATTEMPT_TTL_SECONDS = 600;

    public void markEmailAsVerified(@NonNull String email, long ttlSeconds) {
        try {
            String safeEmail = Objects.requireNonNull(email);
            Duration duration = Duration.ofSeconds(ttlSeconds);

            String key = VERIFICATION_PREFIX + safeEmail;
            // 💡 36번 줄: Objects.requireNonNull로 Duration의 NonNull 보장
            redisTemplate.opsForValue().set(key, "true", Objects.requireNonNull(duration));

            log.info("이메일 인증 상태 저장: {}, TTL: {}초", safeEmail, ttlSeconds);
        } catch (Exception e) {
            log.error("이메일 인증 상태 저장 실패: {}", e.getMessage());
            throw new RuntimeException("이메일 인증 상태 저장 실패", e);
        }
    }

    public boolean isEmailVerified(@NonNull String email) {
        try {
            String key = VERIFICATION_PREFIX + email;
            String verified = redisTemplate.opsForValue().get(key);

            return "true".equals(verified);
        } catch (Exception e) {
            log.warn("이메일 인증 상태 확인 실패: {}", e.getMessage());
            return false;
        }
    }

    public String generateVerificationCode() {
        int code = new Random().nextInt(900000) + 100000;
        return String.valueOf(code);
    }

    public void saveVerificationCode(@NonNull String email, @NonNull String code) {
        try {
            Duration duration = Duration.ofSeconds(VERIFICATION_CODE_TTL_SECONDS);

            String key = VERIFICATION_CODE_PREFIX + email;
            // 💡 67번 줄: Objects.requireNonNull로 Duration의 NonNull 보장
            redisTemplate.opsForValue().set(key, code, Objects.requireNonNull(duration));

            log.info("이메일 인증 코드 저장: {}", email);
        } catch (Exception e) {
            log.error("이메일 인증 코드 저장 실패: {}", e.getMessage());
            throw new RuntimeException("인증 코드 저장 실패", e);
        }
    }

    public boolean verifyCode(@NonNull String email, @NonNull String inputCode) {
        try {
            if (isMaxAttemptsExceeded(email)) {
                throw new RuntimeException("시도 횟수 초과");
            }

            String key = VERIFICATION_CODE_PREFIX + email;
            String storedCode = redisTemplate.opsForValue().get(key);

            if (storedCode == null) {
                incrementAttemptCount(email);
                return false;
            }

            boolean isValid = storedCode.equals(inputCode);

            if (isValid) {
                redisTemplate.delete(key);
                redisTemplate.delete(VERIFICATION_ATTEMPT_PREFIX + email);
            } else {
                incrementAttemptCount(email);
            }

            return isValid;

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("이메일 인증 코드 검증 실패: {}", e.getMessage());
            throw new RuntimeException("검증 실패", e);
        }
    }

    private void incrementAttemptCount(@NonNull String email) {
        try {
            String key = VERIFICATION_ATTEMPT_PREFIX + email;

            Long count = redisTemplate.opsForValue().increment(key);

            if (count != null && count == 1L) {
                // 💡 117번 줄: 생성된 Duration을 Objects.requireNonNull로 감싸서 전달
                redisTemplate.expire(key, Objects.requireNonNull(Duration.ofSeconds(ATTEMPT_TTL_SECONDS)));
            }

        } catch (Exception e) {
            log.error("시도 횟수 증가 실패: {}", e.getMessage());
        }
    }

    private boolean isMaxAttemptsExceeded(@NonNull String email) {
        try {
            String key = VERIFICATION_ATTEMPT_PREFIX + email;
            String countStr = redisTemplate.opsForValue().get(key);

            int count = countStr != null ? Integer.parseInt(countStr) : 0;
            return count >= MAX_ATTEMPT_COUNT;

        } catch (Exception e) {
            return false;
        }
    }

    public int getCurrentAttemptCount(@NonNull String email) {
        try {
            String key = VERIFICATION_ATTEMPT_PREFIX + email;
            String countStr = redisTemplate.opsForValue().get(key);

            return countStr != null ? Integer.parseInt(countStr) : 0;
        } catch (Exception e) {
            return 0;
        }
    }

    public int getRemainingAttemptCount(@NonNull String email) {
        return Math.max(0, MAX_ATTEMPT_COUNT - getCurrentAttemptCount(email));
    }

    public void removeEmailVerification(@NonNull String email) {
        try {
            redisTemplate.delete(VERIFICATION_PREFIX + email);
        } catch (Exception e) {
            log.error("이메일 인증 상태 제거 실패: {}", e.getMessage());
        }
    }
}