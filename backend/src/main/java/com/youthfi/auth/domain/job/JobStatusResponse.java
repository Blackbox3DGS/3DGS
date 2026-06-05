package com.youthfi.auth.domain.job;

import lombok.*;
import java.time.LocalDateTime;
import java.util.*;

@Data @Builder @NoArgsConstructor @AllArgsConstructor
public class JobStatusResponse {
    private String jobId;
    private String status;
    private String statusDescription; // "대기 중", "복원 완료" 등
    private int progress;
    private String currentStep;
    private String customTitle;
    private String thumbnailUrl;
    private LocalDateTime createdAt;
    private LocalDateTime incidentDate;
    private List<Integer> targetIds;
    private String resultUrl;

    public static JobStatusResponse from(JobEntity entity) {
        if (entity == null) return null;
        return JobStatusResponse.builder()
                .jobId(entity.getJobId())
                .status(entity.getStatus().name())
                .statusDescription(entity.getStatus().getDescription())
                .progress(entity.getProgress())
                .currentStep(entity.getCurrentStep())
                .customTitle(entity.getCustomTitle())
                .thumbnailUrl(entity.getThumbnailUrl())
                .createdAt(entity.getCreatedAt())
                .incidentDate(entity.getIncidentDate())
                .targetIds(parseTargetIds(entity.getTargetIds()))
                .resultUrl(entity.getResultUrl())
                .build();
    }

    private static List<Integer> parseTargetIds(String ids) {
        if (ids == null || ids.isEmpty()) return Collections.emptyList();
        return Arrays.stream(ids.split(",")).map(String::trim).map(Integer::parseInt).toList();
    }
}