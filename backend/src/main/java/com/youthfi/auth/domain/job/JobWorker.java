package com.youthfi.auth.domain.job;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.env.Environment; // 추가
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class JobWorker {
    private final JobQueue jobQueue;
    private final JobService jobService;
    private final RestTemplate restTemplate;
    private final Environment env; // 💡 환경 설정을 확인하기 위해 추가

    private volatile boolean running = true;

    @PostConstruct
    public void startWorker() {
        // 💡 테스트 프로파일인 경우 스레드를 시작하지 않음 (빈은 생성되므로 에러 방지)
        if (Arrays.asList(env.getActiveProfiles()).contains("test")) {
            log.info("테스트 환경이므로 JobWorker 스레드를 시작하지 않습니다.");
            return;
        }

        Thread thread = new Thread(() -> {
            log.info("JobWorker 스레드 시작");
            while (running) {
                try {
                    String jobId = jobQueue.pop();
                    if (jobId != null) processJob(jobId);
                    Thread.sleep(500);
                } catch (Exception e) {
                    if (running) log.trace("JobWorker 대기 중...");
                }
            }
        });
        thread.setDaemon(true);
        thread.start();
    }

    @PreDestroy
    public void stopWorker() {
        this.running = false;
    }

    private void processJob(String jobId) {
        try {
            jobService.updateProgress(jobId, 5, "SENDING_TO_AI", "PROCESSING");
            JobStatusResponse job = jobService.getJob(jobId);
            if (job == null) return;
            Map<String, String> request = new HashMap<>();
            request.put("jobId", jobId);
            request.put("filePath", job.getResultUrl());
            restTemplate.postForEntity("http://localhost:8000/analyze", request, String.class);
            jobService.updateProgress(jobId, 10, "AI_PROCESSING", "PROCESSING");
        } catch (Exception e) {
            jobService.updateProgress(jobId, 0, "ERROR", "FAILED");
        }
    }
}