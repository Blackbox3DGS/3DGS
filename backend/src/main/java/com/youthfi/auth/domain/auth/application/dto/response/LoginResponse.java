package com.youthfi.auth.domain.auth.application.dto.response;

/**
 * 로그인 성공 시 응답 데이터
 * (필드가 3개인지 꼭 확인하세요!)
 */
public record LoginResponse(
        String accessToken,
        String refreshToken,
        String name 
) {}