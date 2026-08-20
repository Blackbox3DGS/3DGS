package com.youthfi.auth.domain.auth.application.dto.request;

import jakarta.validation.constraints.NotBlank;

public record TokenReissueRequest(
        @NotBlank(message = "refresh token은 필수입니다.")
        String refreshToken
) {}
