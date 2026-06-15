package com.youthfi.auth.domain.job;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;

import java.util.Objects;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class JobQueue {
    
    private final RedisTemplate<String, Object> redisTemplate;
    private static final String QUEUE_KEY = "job:queue";

    /**
     * 작업을 큐에 추가합니다.
     */
    public void push(@NonNull String jobId) {
        try {
            // null 값이 Redis에 들어가는 것을 방지
            redisTemplate.opsForList().rightPush(QUEUE_KEY, Objects.requireNonNull(jobId, "jobId must not be null"));
            log.info("Job successfully pushed to Redis: {}", jobId);
        } catch (Exception e) {
            log.error("Redis Push 중 에러 발생 (jobId: {}): {}", jobId, e.getMessage());
            throw new RuntimeException("작업 큐 저장에 실패했습니다.", e);
        }
    }

    /**
     * 작업을 큐에서 가져옵니다. 
     * 타임아웃을 설정하여 JobWorker가 주기적으로 상태를 체크할 수 있게 합니다.
     */
    public String pop() {
        try {
            // 5초 동안 데이터가 없으면 null을 반환하고 대기를 해제합니다.
            // 이는 JobWorker의 while(running) 루프가 종료 신호를 감지할 기회를 줍니다.
            Object result = redisTemplate.opsForList().leftPop(QUEUE_KEY, 5, TimeUnit.SECONDS);
            
            if (result != null) {
                return result.toString();
            }
        } catch (Exception e) {
            // Redis 연결 끊김 등의 상황에서도 Worker 스레드가 죽지 않도록 예외 처리
            log.warn("Redis 큐 Pop 대기 중 일시적인 오류 발생: {}", e.getMessage());
        }
        return null;
    }
}