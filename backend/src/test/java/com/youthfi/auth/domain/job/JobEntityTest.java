package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("JobEntity 단위 테스트")
class JobEntityTest {

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
    @DisplayName("엔티티 생성")
    class CreateEntity {

        @Test
        @DisplayName("Builder로 기본 Job 생성 성공")
        void createJob_WithBuilder_Success() {
            // given & when
            JobEntity job = JobEntity.builder()
                    .jobId("job-001")
                    .user(testUser)
                    .originalFileName("blackbox_video.mp4")
                    .status(JobStatus.PENDING)
                    .progress(0)
                    .currentStep("업로드 완료")
                    .build();

            // then
            assertNotNull(job);
            assertEquals("job-001", job.getJobId());
            assertEquals(testUser, job.getUser());
            assertEquals("blackbox_video.mp4", job.getOriginalFileName());
            assertEquals(JobStatus.PENDING, job.getStatus());
            assertEquals(0, job.getProgress());
            assertEquals("업로드 완료", job.getCurrentStep());
        }

        @Test
        @DisplayName("모든 필드를 포함한 Job 생성 성공")
        void createJob_WithAllFields_Success() {
            // given & when
            JobEntity job = JobEntity.builder()
                    .jobId("job-002")
                    .user(testUser)
                    .originalFileName("accident.mp4")
                    .customTitle("강남구 사거리 추돌사고")
                    .thumbnailUrl("https://cdn.example.com/thumb.jpg")
                    .status(JobStatus.COMPLETED)
                    .progress(100)
                    .currentStep("완료")
                    .targetIds("1,2,3")
                    .resultUrl("https://cdn.example.com/output.splat")
                    .trajectoryUrl("https://cdn.example.com/trajectory.json")
                    .build();

            // then
            assertEquals("강남구 사거리 추돌사고", job.getCustomTitle());
            assertEquals("https://cdn.example.com/thumb.jpg", job.getThumbnailUrl());
            assertEquals(JobStatus.COMPLETED, job.getStatus());
            assertEquals(100, job.getProgress());
            assertEquals("1,2,3", job.getTargetIds());
            assertEquals("https://cdn.example.com/output.splat", job.getResultUrl());
            assertEquals("https://cdn.example.com/trajectory.json", job.getTrajectoryUrl());
        }
    }

    @Nested
    @DisplayName("updateTitle() - 제목 변경")
    class UpdateTitle {

        @Test
        @DisplayName("유효한 제목으로 변경 성공")
        void updateTitle_ValidTitle_Success() {
            // given
            JobEntity job = createDefaultJob();

            // when
            job.updateTitle("변경된 제목");

            // then
            assertEquals("변경된 제목", job.getCustomTitle());
        }

        @Test
        @DisplayName("null 제목은 무시됨")
        void updateTitle_NullTitle_Ignored() {
            // given
            JobEntity job = createDefaultJob();
            job.updateTitle("원래 제목");

            // when
            job.updateTitle(null);

            // then
            assertEquals("원래 제목", job.getCustomTitle());
        }

        @Test
        @DisplayName("빈 문자열 제목은 무시됨")
        void updateTitle_EmptyTitle_Ignored() {
            // given
            JobEntity job = createDefaultJob();
            job.updateTitle("원래 제목");

            // when
            job.updateTitle("");

            // then - isBlank()이므로 빈 문자열은 무시
            assertEquals("원래 제목", job.getCustomTitle());
        }

        @Test
        @DisplayName("공백만 있는 제목은 무시됨")
        void updateTitle_BlankTitle_Ignored() {
            // given
            JobEntity job = createDefaultJob();
            job.updateTitle("원래 제목");

            // when
            job.updateTitle("   ");

            // then
            assertEquals("원래 제목", job.getCustomTitle());
        }
    }

    @Nested
    @DisplayName("assignTargets() - 타겟 설정")
    class AssignTargets {

        @Test
        @DisplayName("타겟 ID 목록 설정 성공 및 상태 PROCESSING 전환")
        void assignTargets_ValidList_Success() {
            // given
            JobEntity job = createDefaultJob();
            List<Integer> targets = Arrays.asList(1, 2, 3);

            // when
            job.assignTargets(targets);

            // then
            assertEquals("1,2,3", job.getTargetIds());
            assertEquals(JobStatus.PROCESSING, job.getStatus());
        }

        @Test
        @DisplayName("단일 타겟 ID 설정 성공")
        void assignTargets_SingleTarget_Success() {
            // given
            JobEntity job = createDefaultJob();
            List<Integer> targets = Collections.singletonList(5);

            // when
            job.assignTargets(targets);

            // then
            assertEquals("5", job.getTargetIds());
            assertEquals(JobStatus.PROCESSING, job.getStatus());
        }

        @Test
        @DisplayName("null 타겟 목록은 무시됨")
        void assignTargets_NullList_Ignored() {
            // given
            JobEntity job = createDefaultJob();

            // when
            job.assignTargets(null);

            // then
            assertNull(job.getTargetIds());
            assertEquals(JobStatus.PENDING, job.getStatus()); // 상태 변경 안됨
        }

        @Test
        @DisplayName("빈 타겟 목록은 무시됨")
        void assignTargets_EmptyList_Ignored() {
            // given
            JobEntity job = createDefaultJob();

            // when
            job.assignTargets(Collections.emptyList());

            // then
            assertNull(job.getTargetIds());
            assertEquals(JobStatus.PENDING, job.getStatus());
        }
    }

    @Nested
    @DisplayName("updateProgress() - 진행률 업데이트")
    class UpdateProgress {

        @Test
        @DisplayName("진행률과 상태 업데이트 성공")
        void updateProgress_Success() {
            // given
            JobEntity job = createDefaultJob();

            // when
            job.updateProgress(50, "3D 복원 연산 중", JobStatus.PROCESSING);

            // then
            assertEquals(50, job.getProgress());
            assertEquals("3D 복원 연산 중", job.getCurrentStep());
            assertEquals(JobStatus.PROCESSING, job.getStatus());
        }

        @Test
        @DisplayName("100%로 완료 업데이트")
        void updateProgress_Completed() {
            // given
            JobEntity job = createDefaultJob();

            // when
            job.updateProgress(100, "완료", JobStatus.COMPLETED);

            // then
            assertEquals(100, job.getProgress());
            assertEquals("완료", job.getCurrentStep());
            assertEquals(JobStatus.COMPLETED, job.getStatus());
        }

        @Test
        @DisplayName("실패 상태로 업데이트")
        void updateProgress_Failed() {
            // given
            JobEntity job = createDefaultJob();
            job.updateProgress(50, "처리 중", JobStatus.PROCESSING);

            // when
            job.updateProgress(0, "ERROR", JobStatus.FAILED);

            // then
            assertEquals(0, job.getProgress());
            assertEquals("ERROR", job.getCurrentStep());
            assertEquals(JobStatus.FAILED, job.getStatus());
        }
    }

    @Nested
    @DisplayName("init() - @PrePersist 초기화")
    class Init {

        @Test
        @DisplayName("customTitle이 null일 때 originalFileName으로 초기화")
        void init_NullCustomTitle_SetsOriginalFileName() {
            // given
            JobEntity job = JobEntity.builder()
                    .jobId("job-init-1")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .customTitle(null) // 명시적 null
                    .status(JobStatus.PENDING)
                    .build();

            // when
            job.init();

            // then
            assertEquals("video.mp4", job.getCustomTitle());
        }

        @Test
        @DisplayName("status가 null일 때 PENDING으로 초기화")
        void init_NullStatus_SetsPending() {
            // given
            JobEntity job = JobEntity.builder()
                    .jobId("job-init-2")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .status(null) // 명시적 null
                    .build();

            // when
            job.init();

            // then
            assertEquals(JobStatus.PENDING, job.getStatus());
        }

        @Test
        @DisplayName("customTitle과 status가 이미 설정되어 있으면 유지")
        void init_ExistingValues_Preserved() {
            // given
            JobEntity job = JobEntity.builder()
                    .jobId("job-init-3")
                    .user(testUser)
                    .originalFileName("video.mp4")
                    .customTitle("커스텀 제목")
                    .status(JobStatus.COMPLETED)
                    .build();

            // when
            job.init();

            // then
            assertEquals("커스텀 제목", job.getCustomTitle());
            assertEquals(JobStatus.COMPLETED, job.getStatus());
        }
    }

    // 헬퍼 메서드
    private JobEntity createDefaultJob() {
        return JobEntity.builder()
                .jobId("default-job")
                .user(testUser)
                .originalFileName("default.mp4")
                .status(JobStatus.PENDING)
                .progress(0)
                .currentStep("업로드 완료")
                .build();
    }
}
