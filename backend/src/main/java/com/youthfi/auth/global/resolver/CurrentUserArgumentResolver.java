package com.youthfi.auth.global.resolver;

import org.springframework.core.MethodParameter;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component; // 1. 이 줄이 추가되어야 합니다.
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import com.youthfi.auth.global.annotation.CurrentUser;
import com.youthfi.auth.global.exception.RestApiException;
import static com.youthfi.auth.global.exception.code.status.GlobalErrorStatus._UNAUTHORIZED;
import com.youthfi.auth.global.security.TokenProvider;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;

@Component // 2. 이 한 줄을 추가하면 스프링이 "이 부품을 내가 관리할게!"라고 인식합니다.
@RequiredArgsConstructor
public class CurrentUserArgumentResolver implements HandlerMethodArgumentResolver {

    private final TokenProvider tokenProvider;

    @Override
    public boolean supportsParameter(@NonNull MethodParameter parameter) {
        return parameter.getParameterAnnotation(CurrentUser.class) != null
                && String.class.isAssignableFrom(parameter.getParameterType());
    }

    @Override
    public String resolveArgument(@NonNull MethodParameter parameter,
                                  @Nullable ModelAndViewContainer mavContainer,
                                  @NonNull NativeWebRequest webRequest,
                                  @Nullable WebDataBinderFactory binderFactory) throws Exception {

        HttpServletRequest request = webRequest.getNativeRequest(HttpServletRequest.class);

        if (request == null) {
            throw new RestApiException(_UNAUTHORIZED);
        }

        String token = tokenProvider.getToken(request)
                .orElseThrow(() -> new RestApiException(_UNAUTHORIZED));

        // 토큰 유효성 검증
        if (!tokenProvider.validateToken(token)) {
            throw new RestApiException(_UNAUTHORIZED);
        }

        // Access Token인지 확인
        if (!tokenProvider.isAccessToken(token)) {
            throw new RestApiException(_UNAUTHORIZED);
        }

        return tokenProvider.getId(token)
                .orElseThrow(() -> new RestApiException(_UNAUTHORIZED));
    }
}