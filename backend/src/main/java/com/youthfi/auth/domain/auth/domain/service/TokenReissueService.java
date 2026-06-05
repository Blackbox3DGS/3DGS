package com.youthfi.auth.domain.auth.domain.service;

import java.time.Duration;

import org.springframework.stereotype.Service;

import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.global.exception.RestApiException;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.EXPIRED_MEMBER_JWT;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.INVALID_REFRESH_TOKEN;
import com.youthfi.auth.global.security.TokenProvider;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class TokenReissueService {

    private final TokenProvider tokenProvider;
    private final RefreshTokenService refreshTokenService;
    private final UserService userService;

    public TokenReissueResponse reissue(String refreshToken, String userId) {

        // 존재 유무 검사
        if (!refreshTokenService.isExist(refreshToken, userId)) {
            throw new RestApiException(INVALID_REFRESH_TOKEN);
        }

        // 유저 존재 여부 확인 (🔥 추가)
        userService.findUser(userId);

        // 기존 토큰 삭제
        refreshTokenService.deleteRefreshToken(userId);

        // 새 토큰 발급
        String newAccessToken = tokenProvider.createAccessToken(userId);
        String newRefreshToken = tokenProvider.createRefreshToken(userId);
        Duration duration = tokenProvider.getRemainingDuration(refreshToken)
                .orElseThrow(() -> new RestApiException(EXPIRED_MEMBER_JWT));

        // 저장
        refreshTokenService.saveRefreshToken(userId, newRefreshToken, duration);

        return new TokenReissueResponse(newAccessToken, newRefreshToken);
    }
}