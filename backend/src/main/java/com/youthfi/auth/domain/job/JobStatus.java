package com.youthfi.auth.domain.job;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum JobStatus {
    PENDING("대기 중"),
    PRE_PROCESSING("전처리 중 (객체 분석)"),
    WAITING_FOR_TARGET("타겟 선택 대기"),
    PROCESSING("3D 복원 연산 중"),
    COMPLETED("복원 완료"),
    FAILED("연산 실패");

    private final String description;
}