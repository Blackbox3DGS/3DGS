package com.youthfi.auth.domain.auth.application.usecase;

import java.time.Duration;
import java.util.Optional;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.youthfi.auth.domain.auth.application.dto.request.LoginRequest;
import com.youthfi.auth.domain.auth.application.dto.request.SignUpRequest;
import com.youthfi.auth.domain.auth.application.dto.request.TokenReissueRequest;
import com.youthfi.auth.domain.auth.application.dto.response.LoginResponse;
import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.domain.auth.domain.repository.UserRepository;
import com.youthfi.auth.domain.auth.domain.service.RefreshTokenService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.AuthErrorStatus;
import com.youthfi.auth.global.security.TokenProvider;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;

@Service
@Transactional
@RequiredArgsConstructor
public class UserAuthUseCase {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final TokenProvider tokenProvider;
    private final RefreshTokenService refreshTokenService;

    public void signUp(SignUpRequest request) {
        if (userRepository.existsByUserId(request.userId())) {
            throw new RestApiException(AuthErrorStatus.ALREADY_REGISTERED_USER_ID);
        }
        User user = User.builder()
                .userId(request.userId())
                .password(passwordEncoder.encode(request.password()))
                .email(request.email())
                .name(request.name())
                .build();
        userRepository.save(user);
    }

    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByUserId(request.userId())
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.LOGIN_ERROR));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new RestApiException(AuthErrorStatus.LOGIN_ERROR);
        }

        String accessToken = tokenProvider.createAccessToken(user.getUserId());
        String refreshToken = tokenProvider.createRefreshToken(user.getUserId());
        refreshTokenService.saveRefreshToken(user.getUserId(), refreshToken, Duration.ofDays(14));

        // ✅ 수정된 부분: 이제 사용자의 이름(name)을 응답에 포함합니다.
        return new LoginResponse(accessToken, refreshToken, user.getName());
    }

    public TokenReissueResponse reissueToken(TokenReissueRequest request) {
        String refreshToken = request.refreshToken();

        if (refreshToken == null) {
            throw new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN);
        }

        String userId = tokenProvider.getId(refreshToken)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN));

        if (!userRepository.existsByUserId(userId)) {
            throw new RestApiException(AuthErrorStatus.LOGIN_ERROR);
        }

        if (!refreshTokenService.isExist(refreshToken, userId)) {
            throw new RestApiException(AuthErrorStatus.INVALID_REFRESH_TOKEN);
        }

        Duration duration = tokenProvider.getRemainingDuration(refreshToken)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.EXPIRED_MEMBER_JWT));

        refreshTokenService.deleteRefreshToken(userId);
        String newAccessToken = tokenProvider.createAccessToken(userId);
        String newRefreshToken = tokenProvider.createRefreshToken(userId);
        refreshTokenService.saveRefreshToken(userId, newRefreshToken, duration);

        return new TokenReissueResponse(newAccessToken, newRefreshToken);
    }

    public void logout(HttpServletRequest request) {
        tokenProvider.getToken(request).ifPresent(token -> {
            if (tokenProvider.validateToken(token)) {
                tokenProvider.getId(token).ifPresent(refreshTokenService::deleteRefreshToken);
            }
        });
    }

    public void logout(String userId) {
        refreshTokenService.deleteRefreshToken(userId);
    }

    public String verifyToken(HttpServletRequest request) {
        Optional<String> tokenOpt = tokenProvider.getToken(request);
        if (tokenOpt.isEmpty()) throw new RestApiException(AuthErrorStatus.EMPTY_JWT);
        
        String token = tokenOpt.get();
        if (tokenProvider.validateToken(token)) {
            return tokenProvider.getId(token)
                    .orElseThrow(() -> new RestApiException(AuthErrorStatus.INVALID_ACCESS_TOKEN));
        }
        throw new RestApiException(AuthErrorStatus.INVALID_ACCESS_TOKEN);
    }
}