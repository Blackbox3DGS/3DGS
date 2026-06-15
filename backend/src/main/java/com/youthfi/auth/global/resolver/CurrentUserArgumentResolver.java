package com.youthfi.auth.global.resolver;

import org.springframework.core.MethodParameter;
import org.springframework.lang.NonNull;
import org.springframework.lang.Nullable;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import com.youthfi.auth.domain.auth.domain.entity.User;            // [추가]
import com.youthfi.auth.domain.auth.domain.service.UserService;     // [추가]
import com.youthfi.auth.global.annotation.CurrentUser;
import com.youthfi.auth.global.exception.RestApiException;
import static com.youthfi.auth.global.exception.code.status.GlobalErrorStatus._UNAUTHORIZED;
import com.youthfi.auth.global.security.TokenProvider;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class CurrentUserArgumentResolver implements HandlerMethodArgumentResolver {

    private final TokenProvider tokenProvider;
    private final UserService userService; // [추가] @CurrentUser User 주입 시 DB에서 조회용

    /**
     * @CurrentUser 어노테이션이 붙은 String 또는 User 타입 매개변수를 모두 지원.
     * 기존엔 String만 지원해서 컨트롤러에서 @CurrentUser User user로 받으면 빈 User가 주입되는 버그가 있었음.
     */
    @Override
    public boolean supportsParameter(@NonNull MethodParameter parameter) {
        if (parameter.getParameterAnnotation(CurrentUser.class) == null) return false;
        Class<?> type = parameter.getParameterType();
        return String.class.isAssignableFrom(type) || User.class.isAssignableFrom(type);
    }

    @Override
    public Object resolveArgument(@NonNull MethodParameter parameter,
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

        String userId = tokenProvider.getId(token)
                .orElseThrow(() -> new RestApiException(_UNAUTHORIZED));

        // [추가] 매개변수 타입에 따라 분기: User 엔티티가 필요하면 DB 조회, 아니면 userId 문자열 그대로 반환
        Class<?> type = parameter.getParameterType();
        if (User.class.isAssignableFrom(type)) {
            return userService.findUser(userId); // userId 없으면 INVALID_ACCESS_TOKEN 던짐
        }
        return userId;
    }
}
