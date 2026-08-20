package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Sort;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("JobService 단위 테스트")
class JobServiceTest {

    @Mock
    private ReconstructionJobRepository jobRepository;

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private ValueOperations<String, Object> valueOperations;

    @Mock
    private JobQueue jobQueue;

    @InjectMocks
    private JobService jobService;

    private User testUser;
    private User otherUser;

    @BeforeEach
    void setUp() {
        testUser = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("password")
                .name("테스트유저")
                .build();

        otherUser = User.builder()
                .userId("otheruser")
                .email("other@example.com")
                .password("password")
                .name("다른유저")
                .build();
    }

    @Nested
    @DisplayName("createJob() - 작업 생성")
    class CreateJob {

        @Test
        @DisplayName("작업 생성 성공 - DB 저장 + Redis 동기화 + 큐 push")
        void createJob_Success() {
            // given
            String filePath = "/uploads/video.mp4";
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));

            // when
            String jobId = jobService.createJob(testUser, filePath);

            // then
            assertNotNull(jobId);
            assertFalse(jobId.isEmpty());

            // DB 저장 검증
            ArgumentCaptor<JobEntity> captor = ArgumentCaptor.forClass(JobEntity.class);
            verify(jobRepository, times(1)).save(captor.capture());

            JobEntity savedJob = captor.getValue();
            assertEquals(jobId, savedJob.getJobId());
            assertEquals(testUser, savedJob.getUser());
            assertEquals(filePath, savedJob.getOriginalFileName());
            assertEquals(JobStatus.PENDING, savedJob.getStatus());
            assertEquals(0, savedJob.getProgress());
            assertEquals("업로드 완료", savedJob.getCurrentStep());

            // Redis 동기화 검증
            verify(valueOperations, times(1)).set(eq("job:" + jobId), any(JobStatusResponse.class));

            // 큐 push 검증
            verify(jobQueue, times(1)).push(jobId);
        }
    }

    @Nested
    @DisplayName("searchJobs() - 작업 목록 조회")
    class SearchJobs {

        @Test
        @DisplayName("키워드 기반 제목 검색")
        void searchJobs_WithTitle_Success() {
            // given
            String keyword = "사거리";
            List<JobEntity> expected = List.of(createJobEntity("job-1", "강남구 사거리 추돌사고"));
            when(jobRepository.findByUserUserIdAndCustomTitleContaining(
                    eq("testuser"), eq(keyword), any(Sort.class)))
                    .thenReturn(expected);

            // when
            List<JobEntity> result = jobService.searchJobs(testUser, keyword, null, null);

            // then
            assertEquals(1, result.size());
            assertEquals("강남구 사거리 추돌사고", result.get(0).getCustomTitle());
            verify(jobRepository, times(1)).findByUserUserIdAndCustomTitleContaining(
                    eq("testuser"), eq(keyword), any(Sort.class));
        }

        @Test
        @DisplayName("상태 기반 필터링")
        void searchJobs_WithStatus_Success() {
            // given
            List<JobEntity> expected = List.of(createJobEntity("job-1", "완료된 작업"));
            when(jobRepository.findByUserUserIdAndStatus(
                    eq("testuser"), eq(JobStatus.COMPLETED), any(Sort.class)))
                    .thenReturn(expected);

            // when
            List<JobEntity> result = jobService.searchJobs(testUser, null, JobStatus.COMPLETED, null);

            // then
            assertEquals(1, result.size());
            verify(jobRepository, times(1)).findByUserUserIdAndStatus(
                    eq("testuser"), eq(JobStatus.COMPLETED), any(Sort.class));
        }

        @Test
        @DisplayName("필터 없이 전체 목록 조회")
        void searchJobs_NoFilter_Success() {
            // given
            List<JobEntity> expected = Arrays.asList(
                    createJobEntity("job-1", "작업1"),
                    createJobEntity("job-2", "작업2")
            );
            when(jobRepository.findByUserUserId(eq("testuser"), any(Sort.class)))
                    .thenReturn(expected);

            // when
            List<JobEntity> result = jobService.searchJobs(testUser, null, null, null);

            // then
            assertEquals(2, result.size());
            verify(jobRepository, times(1)).findByUserUserId(eq("testuser"), any(Sort.class));
        }

        @Test
        @DisplayName("빈 문자열 키워드는 전체 목록 조회로 동작")
        void searchJobs_EmptyKeyword_FallsBackToAll() {
            // given
            when(jobRepository.findByUserUserId(eq("testuser"), any(Sort.class)))
                    .thenReturn(Collections.emptyList());

            // when
            List<JobEntity> result = jobService.searchJobs(testUser, "", null, null);

            // then
            verify(jobRepository, times(1)).findByUserUserId(eq("testuser"), any(Sort.class));
            verify(jobRepository, never()).findByUserUserIdAndCustomTitleContaining(anyString(), anyString(), any(Sort.class));
        }

        @Test
        @DisplayName("sortBy='incidentDate' 사용 시 사고날짜 기준 정렬")
        void searchJobs_SortByIncidentDate_UsesCorrectSort() {
            // given
            ArgumentCaptor<Sort> sortCaptor = ArgumentCaptor.forClass(Sort.class);
            when(jobRepository.findByUserUserId(eq("testuser"), sortCaptor.capture()))
                    .thenReturn(Collections.emptyList());

            // when
            jobService.searchJobs(testUser, null, null, "incidentDate");

            // then
            Sort capturedSort = sortCaptor.getValue();
            Sort.Order order = capturedSort.getOrderFor("incidentDate");
            assertNotNull(order);
            assertEquals(Sort.Direction.DESC, order.getDirection());
        }

        @Test
        @DisplayName("title과 status 동시 전달 시 title 우선")
        void searchJobs_TitleAndStatus_TitlePrioritized() {
            // given
            String keyword = "사거리";
            when(jobRepository.findByUserUserIdAndCustomTitleContaining(
                    eq("testuser"), eq(keyword), any(Sort.class)))
                    .thenReturn(Collections.emptyList());

            // when
            jobService.searchJobs(testUser, keyword, JobStatus.COMPLETED, null);

            // then - title 검색이 우선 적용
            verify(jobRepository, times(1)).findByUserUserIdAndCustomTitleContaining(
                    eq("testuser"), eq(keyword), any(Sort.class));
            verify(jobRepository, never()).findByUserUserIdAndStatus(anyString(), any(), any());
        }
    }

    @Nested
    @DisplayName("updateProgress() - 진행률 업데이트")
    class UpdateProgress {

        @Test
        @DisplayName("진행률 업데이트 성공")
        void updateProgress_Success() {
            // given
            JobEntity job = createJobEntity("job-001", "테스트 작업");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);

            // when
            jobService.updateProgress("job-001", 50, "3D 복원 중", "PROCESSING");

            // then
            assertEquals(50, job.getProgress());
            assertEquals("3D 복원 중", job.getCurrentStep());
            assertEquals(JobStatus.PROCESSING, job.getStatus());
            verify(jobRepository, times(1)).save(job);
        }

        @Test
        @DisplayName("존재하지 않는 jobId는 무시됨")
        void updateProgress_JobNotFound_Ignored() {
            // given
            when(jobRepository.findById("nonexistent")).thenReturn(Optional.empty());

            // when
            jobService.updateProgress("nonexistent", 50, "step", "PROCESSING");

            // then
            verify(jobRepository, never()).save(any());
        }

        @Test
        @DisplayName("잘못된 status 문자열은 예외를 삼킴")
        void updateProgress_InvalidStatus_CaughtInternally() {
            // given
            JobEntity job = createJobEntity("job-001", "테스트 작업");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));

            // when & then - 예외가 외부로 전파되지 않음
            assertDoesNotThrow(() ->
                    jobService.updateProgress("job-001", 50, "step", "INVALID_STATUS"));
        }
    }

    @Nested
    @DisplayName("getJob() - 단건 조회")
    class GetJob {

        @Test
        @DisplayName("Redis 캐시 hit 시 캐시에서 반환")
        void getJob_CacheHit_ReturnsFromRedis() {
            // given
            JobStatusResponse cachedResponse = JobStatusResponse.builder()
                    .jobId("job-001")
                    .status("COMPLETED")
                    .progress(100)
                    .build();
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);
            when(valueOperations.get("job:job-001")).thenReturn(cachedResponse);

            // when
            JobStatusResponse result = jobService.getJob("job-001");

            // then
            assertNotNull(result);
            assertEquals("job-001", result.getJobId());
            verify(jobRepository, never()).findById(anyString()); // DB 조회 안함
        }

        @Test
        @DisplayName("Redis 캐시 miss 시 DB에서 조회")
        void getJob_CacheMiss_ReturnsFromDB() {
            // given
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);
            when(valueOperations.get("job:job-001")).thenReturn(null);

            JobEntity entity = createJobEntity("job-001", "DB에서 조회");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(entity));

            // when
            JobStatusResponse result = jobService.getJob("job-001");

            // then
            assertNotNull(result);
            assertEquals("job-001", result.getJobId());
            verify(jobRepository, times(1)).findById("job-001");
        }

        @Test
        @DisplayName("캐시 miss + DB miss 시 null 반환")
        void getJob_NotFound_ReturnsNull() {
            // given
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);
            when(valueOperations.get("job:nonexistent")).thenReturn(null);
            when(jobRepository.findById("nonexistent")).thenReturn(Optional.empty());

            // when
            JobStatusResponse result = jobService.getJob("nonexistent");

            // then
            assertNull(result);
        }

        @Test
        @DisplayName("Redis에 다른 타입의 객체가 저장된 경우 DB로 폴백")
        void getJob_WrongTypeInRedis_FallsBackToDB() {
            // given
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);
            when(valueOperations.get("job:job-001")).thenReturn("wrong type"); // String이 캐시에 있는 경우

            JobEntity entity = createJobEntity("job-001", "폴백 테스트");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(entity));

            // when
            JobStatusResponse result = jobService.getJob("job-001");

            // then
            assertNotNull(result);
            verify(jobRepository, times(1)).findById("job-001");
        }
    }

    @Nested
    @DisplayName("updateCustomTitle() - 제목 변경")
    class UpdateCustomTitle {

        @Test
        @DisplayName("본인 소유 Job 제목 변경 성공")
        void updateCustomTitle_OwnJob_Success() {
            // given
            JobEntity job = createJobEntity("job-001", "원래 제목");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);

            // when
            jobService.updateCustomTitle("job-001", "변경된 제목", testUser);

            // then
            assertEquals("변경된 제목", job.getCustomTitle());
        }

        @Test
        @DisplayName("타인 소유 Job은 제목 변경 불가")
        void updateCustomTitle_OtherUserJob_NotUpdated() {
            // given
            JobEntity job = createJobEntity("job-001", "원래 제목");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));

            // when
            jobService.updateCustomTitle("job-001", "해킹 시도", otherUser);

            // then
            assertEquals("원래 제목", job.getCustomTitle());
        }
    }

    @Nested
    @DisplayName("saveTargetIds() - 타겟 설정")
    class SaveTargetIds {

        @Test
        @DisplayName("본인 소유 Job에 타겟 ID 저장 성공")
        void saveTargetIds_OwnJob_Success() {
            // given
            JobEntity job = createJobEntity("job-001", "테스트");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));
            when(redisTemplate.opsForValue()).thenReturn(valueOperations);

            // when
            jobService.saveTargetIds("job-001", List.of(1, 2, 3), testUser);

            // then
            assertEquals("1,2,3", job.getTargetIds());
            assertEquals(JobStatus.PROCESSING, job.getStatus());
        }

        @Test
        @DisplayName("타인 소유 Job은 타겟 설정 불가")
        void saveTargetIds_OtherUserJob_NotUpdated() {
            // given
            JobEntity job = createJobEntity("job-001", "테스트");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));

            // when
            jobService.saveTargetIds("job-001", List.of(1, 2), otherUser);

            // then
            assertNull(job.getTargetIds());
        }
    }

    @Nested
    @DisplayName("deleteJob() - 작업 삭제")
    class DeleteJob {

        @Test
        @DisplayName("본인 소유 Job 삭제 성공 - DB 삭제 + Redis 캐시 제거")
        void deleteJob_OwnJob_Success() {
            // given
            JobEntity job = createJobEntity("job-001", "삭제 대상");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));
            when(redisTemplate.delete("job:job-001")).thenReturn(true);

            // when
            jobService.deleteJob("job-001", testUser);

            // then
            verify(jobRepository, times(1)).delete(job);
            verify(redisTemplate, times(1)).delete("job:job-001");
        }

        @Test
        @DisplayName("타인 소유 Job은 삭제 불가")
        void deleteJob_OtherUserJob_NotDeleted() {
            // given
            JobEntity job = createJobEntity("job-001", "삭제 불가");
            when(jobRepository.findById("job-001")).thenReturn(Optional.of(job));

            // when
            jobService.deleteJob("job-001", otherUser);

            // then
            verify(jobRepository, never()).delete(any());
            verify(redisTemplate, never()).delete(anyString());
        }

        @Test
        @DisplayName("존재하지 않는 Job 삭제 시 무시")
        void deleteJob_NotFound_Ignored() {
            // given
            when(jobRepository.findById("nonexistent")).thenReturn(Optional.empty());

            // when
            jobService.deleteJob("nonexistent", testUser);

            // then
            verify(jobRepository, never()).delete(any());
        }
    }

    @Nested
    @DisplayName("seedDemoJobs() - 시연용 샘플 데이터 생성")
    class SeedDemoJobs {

        @Test
        @DisplayName("신규 사용자에게 샘플 3개 생성 성공")
        void seedDemoJobs_Success() {
            // given
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));

            // when
            jobService.seedDemoJobs(testUser);

            // then
            verify(jobRepository, times(3)).save(any(JobEntity.class));
        }

        @Test
        @DisplayName("null user 전달 시 아무것도 하지 않음")
        void seedDemoJobs_NullUser_NoOp() {
            // when
            jobService.seedDemoJobs(null);

            // then
            verify(jobRepository, never()).save(any());
        }

        @Test
        @DisplayName("생성된 샘플의 상태가 올바른지 검증")
        void seedDemoJobs_CorrectStatuses() {
            // given
            ArgumentCaptor<JobEntity> captor = ArgumentCaptor.forClass(JobEntity.class);
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));

            // when
            jobService.seedDemoJobs(testUser);

            // then
            verify(jobRepository, times(3)).save(captor.capture());
            List<JobEntity> savedJobs = captor.getAllValues();

            // 첫 번째: COMPLETED, 100%
            assertEquals(JobStatus.COMPLETED, savedJobs.get(0).getStatus());
            assertEquals(100, savedJobs.get(0).getProgress());
            assertEquals("강남구 사거리 추돌사고", savedJobs.get(0).getCustomTitle());

            // 두 번째: PROCESSING, 62%
            assertEquals(JobStatus.PROCESSING, savedJobs.get(1).getStatus());
            assertEquals(62, savedJobs.get(1).getProgress());
            assertEquals("고속도로 측면 충돌", savedJobs.get(1).getCustomTitle());

            // 세 번째: PENDING, 0%
            assertEquals(JobStatus.PENDING, savedJobs.get(2).getStatus());
            assertEquals(0, savedJobs.get(2).getProgress());
            assertEquals("주차장 후진 접촉", savedJobs.get(2).getCustomTitle());
        }

        @Test
        @DisplayName("생성된 샘플은 모두 해당 user에 연결됨")
        void seedDemoJobs_AllLinkedToUser() {
            // given
            ArgumentCaptor<JobEntity> captor = ArgumentCaptor.forClass(JobEntity.class);
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));

            // when
            jobService.seedDemoJobs(testUser);

            // then
            verify(jobRepository, times(3)).save(captor.capture());
            captor.getAllValues().forEach(job ->
                    assertEquals(testUser, job.getUser()));
        }

        @Test
        @DisplayName("각 샘플은 고유 UUID jobId를 가짐")
        void seedDemoJobs_UniqueJobIds() {
            // given
            ArgumentCaptor<JobEntity> captor = ArgumentCaptor.forClass(JobEntity.class);
            when(jobRepository.save(any(JobEntity.class))).thenAnswer(invocation -> invocation.getArgument(0));

            // when
            jobService.seedDemoJobs(testUser);

            // then
            verify(jobRepository, times(3)).save(captor.capture());
            List<JobEntity> savedJobs = captor.getAllValues();

            long uniqueIds = savedJobs.stream()
                    .map(JobEntity::getJobId)
                    .distinct()
                    .count();
            assertEquals(3, uniqueIds, "모든 jobId가 고유해야 합니다");
        }
    }

    // ===================== 헬퍼 메서드 =====================

    private JobEntity createJobEntity(String jobId, String title) {
        return JobEntity.builder()
                .jobId(jobId)
                .user(testUser)
                .originalFileName(title + ".mp4")
                .customTitle(title)
                .status(JobStatus.PENDING)
                .progress(0)
                .currentStep("대기")
                .build();
    }
}
