package com.youthfi.auth.global.resolver;

import com.youthfi.auth.global.annotation.RefreshToken;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.security.TokenProvider;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.core.MethodParameter;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component; // 1. 이 import가 필요합니다.
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.INVALID_REFRESH_TOKEN;
import static com.youthfi.auth.global.exception.code.status.GlobalErrorStatus._UNAUTHORIZED;

@Component // 2. 이 한 줄이 스프링에게 "이건 내가 관리하는 부품이야!"라고 알려주는 역할을 합니다.
@RequiredArgsConstructor
public class RefreshTokenArgumentResolver implements HandlerMethodArgumentResolver {

    private final TokenProvider tokenProvider;

    @Override
    public boolean supportsParameter(@NonNull MethodParameter parameter) {
        return parameter.getParameterAnnotation(RefreshToken.class) != null
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

        // 리프레시 토큰 전용 리졸버이므로, 액세스 토큰이 들어오면 에러 처리
        if (tokenProvider.isAccessToken(token)) {
            throw new RestApiException(INVALID_REFRESH_TOKEN);
        }

        return token;
    }
}