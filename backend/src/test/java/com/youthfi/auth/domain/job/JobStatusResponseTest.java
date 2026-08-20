package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("JobStatusResponse 단위 테스트")
class JobStatusResponseTest {

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("password")
                .name("테스트유저")
                .build();
    }

    @Nested
    @DisplayName("from() - JobEntity → Response 변환")
    class From {

        @Test
        @DisplayName("PENDING 상태 Job 변환 성공")
        void from_PendingJob_Success() {
            // given
            JobEntity entity = JobEntity.builder()
                    .jobId("job-001")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .customTitle("강남구 사거리")
                    .status(JobStatus.PENDING)
                    .progress(0)
                    .currentStep("대기")
                    .build();

            // when
            JobStatusResponse response = JobStatusResponse.from(entity);

            // then
            assertNotNull(response);
            assertEquals("job-001", response.getJobId());
            assertEquals("PENDING", response.getStatus());
            assertEquals("대기 중", response.getStatusDescription());
            assertEquals(0, response.getProgress());
            assertEquals("대기", response.getCurrentStep());
            assertEquals("강남구 사거리", response.getCustomTitle());
        }

        @Test
        @DisplayName("COMPLETED 상태 Job 변환 성공")
        void from_CompletedJob_Success() {
            // given
            JobEntity entity = JobEntity.builder()
                    .jobId("job-002")
                    .user(testUser)
                    .originalFileName("accident.mp4")
                    .customTitle("고속도로 추돌")
                    .status(JobStatus.COMPLETED)
                    .progress(100)
                    .currentStep("완료")
                    .resultUrl("https://cdn.example.com/output.splat")
                    .build();

            // when
            JobStatusResponse response = JobStatusResponse.from(entity);

            // then
            assertEquals("COMPLETED", response.getStatus());
            assertEquals("복원 완료", response.getStatusDescription());
            assertEquals(100, response.getProgress());
            assertEquals("https://cdn.example.com/output.splat", response.getResultUrl());
        }

        @Test
        @DisplayName("targetIds 파싱 성공 (콤마 구분)")
        void from_WithTargetIds_ParsedCorrectly() {
            // given
            JobEntity entity = JobEntity.builder()
                    .jobId("job-003")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .status(JobStatus.PROCESSING)
                    .progress(50)
                    .currentStep("처리 중")
                    .targetIds("1,2,3")
                    .build();

            // when
            JobStatusResponse response = JobStatusResponse.from(entity);

            // then
            assertEquals(List.of(1, 2, 3), response.getTargetIds());
        }

        @Test
        @DisplayName("targetIds가 null이면 빈 리스트 반환")
        void from_NullTargetIds_EmptyList() {
            // given
            JobEntity entity = JobEntity.builder()
                    .jobId("job-004")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .status(JobStatus.PENDING)
                    .progress(0)
                    .currentStep("대기")
                    .targetIds(null)
                    .build();

            // when
            JobStatusResponse response = JobStatusResponse.from(entity);

            // then
            assertNotNull(response.getTargetIds());
            assertEquals(Collections.emptyList(), response.getTargetIds());
        }

        @Test
        @DisplayName("targetIds가 빈 문자열이면 빈 리스트 반환")
        void from_EmptyTargetIds_EmptyList() {
            // given
            JobEntity entity = JobEntity.builder()
                    .jobId("job-005")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .status(JobStatus.PENDING)
                    .progress(0)
                    .currentStep("대기")
                    .targetIds("")
                    .build();

            // when
            JobStatusResponse response = JobStatusResponse.from(entity);

            // then
            assertEquals(Collections.emptyList(), response.getTargetIds());
        }

        @Test
        @DisplayName("null entity 입력 시 null 반환")
        void from_NullEntity_ReturnsNull() {
            // when
            JobStatusResponse response = JobStatusResponse.from(null);

            // then
            assertNull(response);
        }

        @Test
        @DisplayName("모든 JobStatus에 대한 statusDescription 매핑 검증")
        void from_AllStatuses_CorrectDescriptions() {
            // given - 모든 상태별 기대값
            Object[][] statusAndDescriptions = {
                    {JobStatus.PENDING, "대기 중"},
                    {JobStatus.PRE_PROCESSING, "전처리 중 (객체 분석)"},
                    {JobStatus.WAITING_FOR_TARGET, "타겟 선택 대기"},
                    {JobStatus.PROCESSING, "3D 복원 연산 중"},
                    {JobStatus.COMPLETED, "복원 완료"},
                    {JobStatus.FAILED, "연산 실패"},
            };

            for (Object[] pair : statusAndDescriptions) {
                JobStatus status = (JobStatus) pair[0];
                String expectedDescription = (String) pair[1];

                JobEntity entity = JobEntity.builder()
                        .jobId("job-status-" + status.name())
                        .user(testUser)
                        .originalFileName("video.mp4")
                        .status(status)
                        .progress(0)
                        .currentStep("test")
                        .build();

                // when
                JobStatusResponse response = JobStatusResponse.from(entity);

                // then
                assertEquals(status.name(), response.getStatus(),
                        "status 이름 불일치: " + status.name());
                assertEquals(expectedDescription, response.getStatusDescription(),
                        "statusDescription 불일치: " + status.name());
            }
        }
    }
}
