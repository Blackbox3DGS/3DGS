package com.youthfi.auth.domain.auth.application.dto.response;

public record TokenReissueResponse(
        String accessToken,
        String refreshToken
) {}