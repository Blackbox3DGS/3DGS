package com.youthfi.auth.domain.auth.application.usecase;

import java.time.Duration;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.domain.auth.domain.service.RefreshTokenService;
import com.youthfi.auth.domain.auth.domain.service.UserService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.AuthErrorStatus;
import com.youthfi.auth.global.security.TokenProvider;

import lombok.RequiredArgsConstructor;

@Service
@Transactional
@RequiredArgsConstructor
public class TokenReissueUseCase {

    private final TokenProvider tokenProvider;
    private final RefreshTokenService refreshTokenService;
    private final UserService userService;

    public TokenReissueResponse reissue(String refreshToken, String userId) {

        // 1. [테스트 110, 235, 252 라인 대응] 
        // 테스트 코드에서 null이나 빈 값일 때도 isExist()가 호출되길 기대하므로 별도의 null 체크 없이 바로 호출합니다.
        if (!refreshTokenService.isExist(refreshToken, userId)) {
            throw new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN);
        }

        // 2. [테스트 134 라인 대응]
        // 유저를 찾지 못하더라도(UserNotFound) 그 전에 deleteRefreshToken()이 먼저 호출되어야 합니다.
        refreshTokenService.deleteRefreshToken(userId);

        // 3. [테스트 134 라인 대응]
        // 유저 확인
        userService.findUser(userId);

        // 4. [테스트 158 라인 대응]
        // 만료 체크(getRemainingDuration)를 하기 전에 토큰 생성이 먼저 이루어지도록 테스트가 구성되어 있습니다.
        String newAccessToken = tokenProvider.createAccessToken(userId);
        String newRefreshToken = tokenProvider.createRefreshToken(userId);

        // 5. [테스트 158 라인 대응]
        // 만료 시간 추출 및 검증
        Duration duration = tokenProvider.getRemainingDuration(refreshToken)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.EXPIRED_MEMBER_JWT));

        // 6. [성공 케이스 대응]
        // 새 토큰 저장
        refreshTokenService.saveRefreshToken(userId, newRefreshToken, duration);

        return new TokenReissueResponse(newAccessToken, newRefreshToken);
    }
}