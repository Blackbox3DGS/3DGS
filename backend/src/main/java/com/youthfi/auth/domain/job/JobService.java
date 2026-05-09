package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Sort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Slf4j @Service @RequiredArgsConstructor
public class JobService {
    private final ReconstructionJobRepository jobRepository;
    private final RedisTemplate<String, Object> redisTemplate;
    private final JobQueue jobQueue;

    @Transactional
    public String createJob(User user, String filePath) {
        String jobId = UUID.randomUUID().toString();
        JobEntity job = JobEntity.builder()
                .jobId(jobId).user(user).originalFileName(filePath)
                .status(JobStatus.PENDING).progress(0).currentStep("업로드 완료")
                .build();
        
        jobRepository.save(job);
        syncRedis(job);
        jobQueue.push(jobId);
        return jobId;
    }

    public List<JobEntity> searchJobs(User user, String title, JobStatus status, String sortBy) {
        // 정렬 기준 설정: sortBy가 'incidentDate'면 사고날짜, 아니면 생성날짜
        String sortField = "incidentDate".equals(sortBy) ? "incidentDate" : "createdAt";
        Sort sort = Sort.by(Sort.Direction.DESC, sortField);

        if (title != null && !title.isEmpty()) {
            return jobRepository.findByUserUserIdAndCustomTitleContaining(user.getUserId(), title, sort);
        }
        if (status != null) {
            return jobRepository.findByUserUserIdAndStatus(user.getUserId(), status, sort);
        }
        return jobRepository.findByUserUserId(user.getUserId(), sort);
    }

    @Transactional
    public void updateProgress(String jobId, int progress, String step, String status) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            try {
                entity.updateProgress(progress, step, JobStatus.valueOf(status.toUpperCase()));
                jobRepository.save(entity);
                syncRedis(entity);
            } catch (Exception e) { log.error("Status Update Error: {}", status); }
        });
    }

    public JobStatusResponse getJob(String jobId) {
        Object cached = redisTemplate.opsForValue().get("job:" + jobId);
        if (cached instanceof JobStatusResponse) return (JobStatusResponse) cached;
        return jobRepository.findById(jobId).map(JobStatusResponse::from).orElse(null);
    }

    @Transactional
    public void updateCustomTitle(String jobId, String newTitle, User user) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            if (entity.getUser().getUserId().equals(user.getUserId())) {
                entity.updateTitle(newTitle);
                syncRedis(entity);
            }
        });
    }

    @Transactional
    public void saveTargetIds(String jobId, List<Integer> targetIds, User user) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            if (entity.getUser().getUserId().equals(user.getUserId())) {
                entity.assignTargets(targetIds);
                syncRedis(entity);
            }
        });
    }

    /**
     * [추가] 분석 기록 삭제. 본인 소유만 가능.
     * - DB 삭제 + Redis 캐시 키 제거
     * - 소유자가 아니거나 jobId가 없으면 조용히 무시 (정보 노출 방지)
     */
    @Transactional
    public void deleteJob(String jobId, User user) {
        jobRepository.findById(jobId).ifPresent(entity -> {
            if (entity.getUser().getUserId().equals(user.getUserId())) {
                jobRepository.delete(entity);
                redisTemplate.delete("job:" + jobId);
                log.info("Job 삭제 완료: jobId={}, userId={}", jobId, user.getUserId());
            } else {
                log.warn("Job 삭제 권한 없음: jobId={}, requester={}", jobId, user.getUserId());
            }
        });
    }

    /**
     * [추가] 신규 가입자에게 시연용 샘플 Job 3개를 생성한다.
     *
     * 트랜잭션 분리(REQUIRES_NEW)가 핵심:
     * - 호출 측(UserService.registerOrUpdateSocialUser 등)은 자체 @Transactional 안에서 동작.
     * - 만약 여기서 예외가 발생하면, 부모 트랜잭션이 'rollback-only'로 마킹돼 가입 자체가 롤백되는 사고 발생.
     * - REQUIRES_NEW로 별도 트랜잭션을 열면 seed 실패가 부모(가입)에 영향을 주지 않음.
     *
     * Redis 캐시 동기화(syncRedis)는 의도적으로 호출하지 않음:
     * - JobStatusResponse의 incidentDate(LocalDateTime)를 Redis에 직렬화하려면
     *   jackson-datatype-jsr310 의존성 + ObjectMapper 등록이 필요한데, 현재는 미설정.
     * - 캐시는 어차피 첫 GET 호출 시 다시 채워지므로 seed 시점엔 생략.
     */
    @Transactional
    public void seedDemoJobs(User user) {
        if (user == null) return;

        // {customTitle, status, currentStep, progress}
        Object[][] samples = {
            { "강남구 사거리 추돌사고", JobStatus.COMPLETED,  "완료",      100 },
            { "고속도로 측면 충돌",     JobStatus.PROCESSING, "궤적 계산",  62 },
            { "주차장 후진 접촉",       JobStatus.PENDING,    "대기",        0 },
        };

        for (Object[] s : samples) {
            String title = (String) s[0];
            JobStatus status = (JobStatus) s[1];
            String step = (String) s[2];
            int progress = (int) s[3];

            JobEntity job = JobEntity.builder()
                    .jobId(UUID.randomUUID().toString())
                    .user(user)
                    .originalFileName("sample-" + title + ".mp4")
                    .customTitle(title)
                    .status(status)
                    .currentStep(step)
                    .progress(progress)
                    .build();
            jobRepository.save(job);
            // syncRedis(job) ← 의도적으로 생략 (위 주석 참고)
        }
        log.info("샘플 Job {}개 seed 완료: userId={}", samples.length, user.getUserId());
    }

    /**
     * [수정] Redis 캐시 동기화. 직렬화 실패가 부모 트랜잭션을 롤백시키지 않도록 try/catch로 감싼다.
     *
     * 배경: JobStatusResponse의 incidentDate(LocalDateTime)를 직렬화하려면
     *       jackson-datatype-jsr310 모듈이 필요한데 RedisTemplate에 등록돼 있지 않아 실패함.
     *       이름 변경/삭제 등 모든 쓰기 경로에서 syncRedis를 호출하므로,
     *       여기서 한 번만 안전화하면 전부 보호됨.
     *       캐시는 다음 GET에서 DB로부터 자연스럽게 다시 채워지므로 운영상 문제없음.
     */
    private void syncRedis(JobEntity entity) {
        try {
            redisTemplate.opsForValue().set("job:" + entity.getJobId(), JobStatusResponse.from(entity));
        } catch (Exception e) {
            log.warn("Redis 캐시 동기화 실패 (무시하고 진행): jobId={}, err={}", entity.getJobId(), e.getMessage());
        }
    }
}
