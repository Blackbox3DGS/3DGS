package com.youthfi.auth.domain.auth.application.dto.request;

import jakarta.validation.constraints.NotBlank;

public record SocialLoginRequest(
        @NotBlank(message = "Authorization code는 필수입니다.")
        String code
) {}


