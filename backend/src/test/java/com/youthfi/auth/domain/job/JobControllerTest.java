package com.youthfi.auth.domain.job;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.global.annotation.CurrentUser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * JobController 단위 테스트
 * - @CurrentUser 리졸버를 Mock으로 대체하여 Security 우회
 * - Standalone MockMvc 설정으로 Controller 로직만 격리 테스트
 */
@DisplayName("JobController 단위 테스트")
class JobControllerTest {

    private MockMvc mockMvc;

    private JobService jobService;

    private ObjectMapper objectMapper;

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("password")
                .name("테스트유저")
                .build();

        jobService = mock(JobService.class);
        objectMapper = new ObjectMapper();

        // @CurrentUser 어노테이션이 붙은 파라미터를 testUser로 자동 주입하는 리졸버
        HandlerMethodArgumentResolver currentUserResolver = new HandlerMethodArgumentResolver() {
            @Override
            public boolean supportsParameter(@NonNull MethodParameter parameter) {
                return parameter.hasParameterAnnotation(CurrentUser.class);
            }

            @Override
            public Object resolveArgument(@NonNull MethodParameter parameter,
                                          @Nullable ModelAndViewContainer mavContainer,
                                          @NonNull NativeWebRequest webRequest,
                                          @Nullable WebDataBinderFactory binderFactory) {
                if (User.class.isAssignableFrom(parameter.getParameterType())) {
                    return testUser;
                }
                return testUser.getUserId();
            }
        };

        mockMvc = MockMvcBuilders
                .standaloneSetup(new JobController(jobService))
                .setCustomArgumentResolvers(currentUserResolver)
                .build();
    }

    @Nested
    @DisplayName("GET /api/v1/reconstruction - 내 작업 목록 조회")
    class GetMyJobs {

        @Test
        @DisplayName("필터 없이 전체 목록 조회 성공")
        void getMyJobs_NoFilter_Success() throws Exception {
            // given
            JobEntity job1 = createJobEntity("job-1", "작업 1", JobStatus.COMPLETED, 100);
            JobEntity job2 = createJobEntity("job-2", "작업 2", JobStatus.PENDING, 0);
            when(jobService.searchJobs(any(User.class), isNull(), isNull(), eq("createdAt")))
                    .thenReturn(Arrays.asList(job1, job2));

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.code").value("COMMON200"))
                    .andExpect(jsonPath("$.result", hasSize(2)))
                    .andExpect(jsonPath("$.result[0].jobId").value("job-1"))
                    .andExpect(jsonPath("$.result[1].jobId").value("job-2"));
        }

        @Test
        @DisplayName("키워드 검색 성공")
        void getMyJobs_WithKeyword_Success() throws Exception {
            // given
            JobEntity job = createJobEntity("job-1", "강남구 사거리", JobStatus.COMPLETED, 100);
            when(jobService.searchJobs(any(User.class), eq("강남구"), isNull(), eq("createdAt")))
                    .thenReturn(List.of(job));

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction")
                            .param("keyword", "강남구"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result", hasSize(1)))
                    .andExpect(jsonPath("$.result[0].customTitle").value("강남구 사거리"));
        }

        @Test
        @DisplayName("상태 필터링 성공")
        void getMyJobs_WithStatus_Success() throws Exception {
            // given
            when(jobService.searchJobs(any(User.class), isNull(), eq(JobStatus.COMPLETED), eq("createdAt")))
                    .thenReturn(Collections.emptyList());

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction")
                            .param("status", "COMPLETED"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result", hasSize(0)));
        }

        @Test
        @DisplayName("빈 목록 반환 성공")
        void getMyJobs_EmptyList_Success() throws Exception {
            // given
            when(jobService.searchJobs(any(User.class), isNull(), isNull(), eq("createdAt")))
                    .thenReturn(Collections.emptyList());

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result", hasSize(0)));
        }
    }

    @Nested
    @DisplayName("GET /api/v1/reconstruction/{jobId} - 단건 조회")
    class GetStatus {

        @Test
        @DisplayName("작업 상태 조회 성공")
        void getStatus_Success() throws Exception {
            // given
            JobStatusResponse response = JobStatusResponse.builder()
                    .jobId("job-001")
                    .status("PROCESSING")
                    .statusDescription("3D 복원 연산 중")
                    .progress(65)
                    .currentStep("궤적 계산")
                    .customTitle("강남구 사거리")
                    .build();
            when(jobService.getJob("job-001")).thenReturn(response);

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction/job-001"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result.jobId").value("job-001"))
                    .andExpect(jsonPath("$.result.status").value("PROCESSING"))
                    .andExpect(jsonPath("$.result.progress").value(65))
                    .andExpect(jsonPath("$.result.customTitle").value("강남구 사거리"));
        }

        @Test
        @DisplayName("존재하지 않는 작업 조회 시 null 반환")
        void getStatus_NotFound() throws Exception {
            // given
            when(jobService.getJob("nonexistent")).thenReturn(null);

            // when & then
            mockMvc.perform(get("/api/v1/reconstruction/nonexistent"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result").doesNotExist());
        }
    }

    @Nested
    @DisplayName("PATCH /api/v1/reconstruction/{jobId}/title - 제목 변경")
    class RenameJob {

        @Test
        @DisplayName("제목 변경 성공")
        void renameJob_Success() throws Exception {
            // given
            doNothing().when(jobService).updateCustomTitle(eq("job-001"), eq("새로운 제목"), any(User.class));

            // when & then
            mockMvc.perform(patch("/api/v1/reconstruction/job-001/title")
                            .param("newTitle", "새로운 제목"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.code").value("COMMON200"))
                    .andExpect(jsonPath("$.result").value("제목 변경 완료"));

            verify(jobService, times(1)).updateCustomTitle("job-001", "새로운 제목", testUser);
        }
    }

    @Nested
    @DisplayName("POST /api/v1/reconstruction/{jobId}/target - 타겟 설정")
    class SetTarget {

        @Test
        @DisplayName("타겟 설정 성공")
        void setTarget_Success() throws Exception {
            // given
            TargetRequest request = new TargetRequest();
            request.setTargetIds(List.of(1, 2, 3));
            doNothing().when(jobService).saveTargetIds(eq("job-001"), eq(List.of(1, 2, 3)), any(User.class));

            // when & then
            mockMvc.perform(post("/api/v1/reconstruction/job-001/target")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.result").value("타겟 설정 완료"));

            verify(jobService, times(1)).saveTargetIds(eq("job-001"), eq(List.of(1, 2, 3)), eq(testUser));
        }
    }

    @Nested
    @DisplayName("DELETE /api/v1/reconstruction/{jobId} - 작업 삭제")
    class DeleteJob {

        @Test
        @DisplayName("작업 삭제 성공")
        void deleteJob_Success() throws Exception {
            // given
            doNothing().when(jobService).deleteJob(eq("job-001"), any(User.class));

            // when & then
            mockMvc.perform(delete("/api/v1/reconstruction/job-001"))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.code").value("COMMON200"))
                    .andExpect(jsonPath("$.result").value("삭제 완료"));

            verify(jobService, times(1)).deleteJob("job-001", testUser);
        }
    }

    // ===================== 헬퍼 메서드 =====================

    private JobEntity createJobEntity(String jobId, String title, JobStatus status, int progress) {
        return JobEntity.builder()
                .jobId(jobId)
                .user(testUser)
                .originalFileName(title + ".mp4")
                .customTitle(title)
                .status(status)
                .progress(progress)
                .currentStep(status == JobStatus.COMPLETED ? "완료" : "대기")
                .build();
    }
}
