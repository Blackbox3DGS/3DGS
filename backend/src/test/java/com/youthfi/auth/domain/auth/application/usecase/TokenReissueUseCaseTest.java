package com.youthfi.auth.domain.auth.application.usecase;

import java.time.Duration;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import org.mockito.junit.jupiter.MockitoExtension;

import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.domain.auth.domain.service.RefreshTokenService;
import com.youthfi.auth.domain.auth.domain.service.UserService;
import com.youthfi.auth.global.exception.RestApiException;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.EXPIRED_MEMBER_JWT;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.INVALID_REFRESH_TOKEN;
import com.youthfi.auth.global.security.TokenProvider;

@ExtendWith(MockitoExtension.class)
@DisplayName("TokenReissueUseCase 테스트")
class TokenReissueUseCaseTest {

    @Mock
    private TokenProvider tokenProvider;

    @Mock
    private RefreshTokenService refreshTokenService;

    @Mock
    private UserService userService;

    @InjectMocks
    private TokenReissueUseCase tokenReissueUseCase;

    private static final String VALID_REFRESH_TOKEN = "valid.refresh.token";
    private static final String VALID_USER_ID = "testuser";
    private static final String NEW_ACCESS_TOKEN = "new.access.token";
    private static final String NEW_REFRESH_TOKEN = "new.refresh.token";
    private static final Duration VALID_DURATION = Duration.ofDays(7);

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = User.builder()
                .userId(VALID_USER_ID)
                .email("test@example.com")
                .password("encodedPassword")
                .name("Test User")
                .birth("1990-01-01")
                .build();
    }

    @Test
    @DisplayName("토큰 재발급 성공")
    void reissue_Success() {
        // given
        when(refreshTokenService.isExist(VALID_REFRESH_TOKEN, VALID_USER_ID)).thenReturn(true);
        doNothing().when(refreshTokenService).deleteRefreshToken(VALID_USER_ID);
        when(userService.findUser(VALID_USER_ID)).thenReturn(testUser);
        when(tokenProvider.createAccessToken(VALID_USER_ID)).thenReturn(NEW_ACCESS_TOKEN);
        when(tokenProvider.createRefreshToken(VALID_USER_ID)).thenReturn(NEW_REFRESH_TOKEN);
        when(tokenProvider.getRemainingDuration(VALID_REFRESH_TOKEN)).thenReturn(Optional.of(VALID_DURATION));
        doNothing().when(refreshTokenService).saveRefreshToken(eq(VALID_USER_ID), eq(NEW_REFRESH_TOKEN), eq(VALID_DURATION));

        // when
        TokenReissueResponse response = tokenReissueUseCase.reissue(VALID_REFRESH_TOKEN, VALID_USER_ID);

        // then
        assertNotNull(response);
        assertEquals(NEW_ACCESS_TOKEN, response.accessToken());
        assertEquals(NEW_REFRESH_TOKEN, response.refreshToken());

        verify(refreshTokenService, times(1)).isExist(VALID_REFRESH_TOKEN, VALID_USER_ID);
        verify(refreshTokenService, times(1)).deleteRefreshToken(VALID_USER_ID);
        verify(userService, times(1)).findUser(VALID_USER_ID);
        verify(tokenProvider, times(1)).createAccessToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).createRefreshToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).getRemainingDuration(VALID_REFRESH_TOKEN);
        verify(refreshTokenService, times(1)).saveRefreshToken(VALID_USER_ID, NEW_REFRESH_TOKEN, VALID_DURATION);
    }

    @Test
    @DisplayName("리프레시 토큰이 존재하지 않을 때 INVALID_REFRESH_TOKEN 예외 발생")
    void reissue_RefreshTokenNotExist_ThrowsException() {
        // given
        when(refreshTokenService.isExist(VALID_REFRESH_TOKEN, VALID_USER_ID)).thenReturn(false);

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            tokenReissueUseCase.reissue(VALID_REFRESH_TOKEN, VALID_USER_ID);
        });

        assertEquals(INVALID_REFRESH_TOKEN.getCode(), exception.getErrorCode());
        verify(refreshTokenService, times(1)).isExist(VALID_REFRESH_TOKEN, VALID_USER_ID);
        verify(refreshTokenService, never()).deleteRefreshToken(anyString());
        verify(userService, never()).findUser(anyString());
        verify(tokenProvider, never()).createAccessToken(anyString());
        verify(tokenProvider, never()).createRefreshToken(anyString());
        verify(tokenProvider, never()).getRemainingDuration(anyString());
        verify(refreshTokenService, never()).saveRefreshToken(anyString(), anyString(), any(Duration.class));
    }

    @Test
    @DisplayName("사용자를 찾을 수 없을 때 예외 발생")
    void reissue_UserNotFound_ThrowsException() {
        // given
        when(refreshTokenService.isExist(VALID_REFRESH_TOKEN, VALID_USER_ID)).thenReturn(true);
        doNothing().when(refreshTokenService).deleteRefreshToken(VALID_USER_ID);
        doThrow(new RuntimeException("사용자를 찾을 수 없습니다"))
                .when(userService).findUser(VALID_USER_ID);

        // when & then
        assertThrows(RuntimeException.class, () -> {
            tokenReissueUseCase.reissue(VALID_REFRESH_TOKEN, VALID_USER_ID);
        });

        verify(refreshTokenService, times(1)).isExist(VALID_REFRESH_TOKEN, VALID_USER_ID);
        verify(refreshTokenService, times(1)).deleteRefreshToken(VALID_USER_ID);
        verify(userService, times(1)).findUser(VALID_USER_ID);
        verify(tokenProvider, never()).createAccessToken(anyString());
        verify(tokenProvider, never()).createRefreshToken(anyString());
        verify(tokenProvider, never()).getRemainingDuration(anyString());
        verify(refreshTokenService, never()).saveRefreshToken(anyString(), anyString(), any(Duration.class));
    }

    @Test
    @DisplayName("리프레시 토큰 만료 시간을 가져올 수 없을 때 EXPIRED_MEMBER_JWT 예외 발생")
    void reissue_ExpiredToken_ThrowsException() {
        // given
        when(refreshTokenService.isExist(VALID_REFRESH_TOKEN, VALID_USER_ID)).thenReturn(true);
        doNothing().when(refreshTokenService).deleteRefreshToken(VALID_USER_ID);
        when(userService.findUser(VALID_USER_ID)).thenReturn(testUser);
        when(tokenProvider.getRemainingDuration(VALID_REFRESH_TOKEN)).thenReturn(Optional.empty());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            tokenReissueUseCase.reissue(VALID_REFRESH_TOKEN, VALID_USER_ID);
        });

        assertEquals(EXPIRED_MEMBER_JWT.getCode(), exception.getErrorCode());
        verify(refreshTokenService, times(1)).isExist(VALID_REFRESH_TOKEN, VALID_USER_ID);
        verify(refreshTokenService, times(1)).deleteRefreshToken(VALID_USER_ID);
        verify(userService, times(1)).findUser(VALID_USER_ID);
        verify(tokenProvider, times(1)).createAccessToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).createRefreshToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).getRemainingDuration(VALID_REFRESH_TOKEN);
        verify(refreshTokenService, never()).saveRefreshToken(anyString(), anyString(), any(Duration.class));
    }

    @Test
    @DisplayName("새 토큰 저장 실패 시 예외 발생")
    void reissue_SaveTokenFailed_ThrowsException() {
        // given
        when(refreshTokenService.isExist(VALID_REFRESH_TOKEN, VALID_USER_ID)).thenReturn(true);
        doNothing().when(refreshTokenService).deleteRefreshToken(VALID_USER_ID);
        when(userService.findUser(VALID_USER_ID)).thenReturn(testUser);
        when(tokenProvider.createAccessToken(VALID_USER_ID)).thenReturn(NEW_ACCESS_TOKEN);
        when(tokenProvider.createRefreshToken(VALID_USER_ID)).thenReturn(NEW_REFRESH_TOKEN);
        when(tokenProvider.getRemainingDuration(VALID_REFRESH_TOKEN)).thenReturn(Optional.of(VALID_DURATION));
        doThrow(new RuntimeException("토큰 저장 실패"))
                .when(refreshTokenService).saveRefreshToken(eq(VALID_USER_ID), eq(NEW_REFRESH_TOKEN), eq(VALID_DURATION));

        // when & then
        assertThrows(RuntimeException.class, () -> {
            tokenReissueUseCase.reissue(VALID_REFRESH_TOKEN, VALID_USER_ID);
        });

        verify(refreshTokenService, times(1)).isExist(VALID_REFRESH_TOKEN, VALID_USER_ID);
        verify(refreshTokenService, times(1)).deleteRefreshToken(VALID_USER_ID);
        verify(userService, times(1)).findUser(VALID_USER_ID);
        verify(tokenProvider, times(1)).createAccessToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).createRefreshToken(VALID_USER_ID);
        verify(tokenProvider, times(1)).getRemainingDuration(VALID_REFRESH_TOKEN);
        verify(refreshTokenService, times(1)).saveRefreshToken(VALID_USER_ID, NEW_REFRESH_TOKEN, VALID_DURATION);
    }

    @Test
    @DisplayName("다양한 사용자 ID로 토큰 재발급 테스트")
    void reissue_DifferentUserIds_Success() {
        // given
        String[] userIds = {"user1", "user2", "admin"};
        String[] refreshTokens = {"token1", "token2", "token3"};
        String[] accessTokens = {"access1", "access2", "access3"};
        String[] newRefreshTokens = {"newToken1", "newToken2", "newToken3"};

        for (int i = 0; i < userIds.length; i++) {
            // given
            when(refreshTokenService.isExist(refreshTokens[i], userIds[i])).thenReturn(true);
            doNothing().when(refreshTokenService).deleteRefreshToken(userIds[i]);
            when(userService.findUser(userIds[i])).thenReturn(testUser);
            when(tokenProvider.createAccessToken(userIds[i])).thenReturn(accessTokens[i]);
            when(tokenProvider.createRefreshToken(userIds[i])).thenReturn(newRefreshTokens[i]);
            when(tokenProvider.getRemainingDuration(refreshTokens[i])).thenReturn(Optional.of(VALID_DURATION));
            doNothing().when(refreshTokenService).saveRefreshToken(eq(userIds[i]), eq(newRefreshTokens[i]), eq(VALID_DURATION));

            // when
            TokenReissueResponse response = tokenReissueUseCase.reissue(refreshTokens[i], userIds[i]);

            // then
            assertNotNull(response);
            assertEquals(accessTokens[i], response.accessToken());
            assertEquals(newRefreshTokens[i], response.refreshToken());
        }
    }

    @Test
    @DisplayName("빈 문자열 토큰으로 재발급 시도 시 예외 발생")
    void reissue_EmptyToken_ThrowsException() {
        // given
        String emptyToken = "";
        when(refreshTokenService.isExist(emptyToken, VALID_USER_ID)).thenReturn(false);

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            tokenReissueUseCase.reissue(emptyToken, VALID_USER_ID);
        });

        assertEquals(INVALID_REFRESH_TOKEN.getCode(), exception.getErrorCode());
        verify(refreshTokenService, times(1)).isExist(emptyToken, VALID_USER_ID);
    }

    @Test
    @DisplayName("null 토큰으로 재발급 시도 시 예외 발생")
    void reissue_NullToken_ThrowsException() {
        // given
        String nullToken = null;
        when(refreshTokenService.isExist(nullToken, VALID_USER_ID)).thenReturn(false);

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            tokenReissueUseCase.reissue(nullToken, VALID_USER_ID);
        });

        assertEquals(INVALID_REFRESH_TOKEN.getCode(), exception.getErrorCode());
        verify(refreshTokenService, times(1)).isExist(nullToken, VALID_USER_ID);
    }
}
