package com.youthfi.auth.global.interceptor;

import com.youthfi.auth.domain.auth.domain.service.TokenBlacklistService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.security.TokenProvider;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Objects; // 추가됨

import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.EMPTY_JWT;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.EXPIRED_MEMBER_JWT;

@Component
@RequiredArgsConstructor
public class JwtBlacklistInterceptor implements HandlerInterceptor {

    private final TokenProvider tokenProvider;
    private final TokenBlacklistService tokenBlacklistService;

    @Override
    public boolean preHandle(@NonNull HttpServletRequest req, @NonNull HttpServletResponse res, @NonNull Object handler) {
        String token = tokenProvider.getToken(req)
                .orElseThrow(() -> new RestApiException(EMPTY_JWT));

        // 29번 줄: Objects.requireNonNull()로 감싸서 IDE의 Null safety 경고 해결
        boolean isBlack = tokenBlacklistService.isBlacklisted(Objects.requireNonNull(token));
        
        if (isBlack) {
            throw new RestApiException(EXPIRED_MEMBER_JWT);
        }
        return true;
    }
}