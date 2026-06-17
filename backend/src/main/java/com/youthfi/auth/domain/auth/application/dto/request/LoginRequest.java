package com.youthfi.auth.domain.auth.application.dto.request;

import jakarta.validation.constraints.NotBlank;

public record LoginRequest(
        @NotBlank(message = "사용자 ID는 필수입니다.")
        String userId,

        @NotBlank(message = "비밀번호는 필수입니다.")
        String password
) {}