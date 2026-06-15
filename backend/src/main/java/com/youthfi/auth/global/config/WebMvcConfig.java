package com.youthfi.auth.global.config;

import java.util.List;
import java.util.Objects;
import org.springframework.context.annotation.Configuration;
import org.springframework.lang.NonNull;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import com.youthfi.auth.global.interceptor.JwtBlacklistInterceptor;
import com.youthfi.auth.global.resolver.CurrentUserArgumentResolver;
import com.youthfi.auth.global.resolver.RefreshTokenArgumentResolver;
import lombok.RequiredArgsConstructor;

@Configuration
@RequiredArgsConstructor
public class WebMvcConfig implements WebMvcConfigurer {

    private final CurrentUserArgumentResolver currentUserArgumentResolver;
    private final RefreshTokenArgumentResolver refreshTokenArgumentResolver;
    private final JwtBlacklistInterceptor jwtBlacklistInterceptor;

    @Override
    public void addArgumentResolvers(@NonNull List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(Objects.requireNonNull(currentUserArgumentResolver));
        resolvers.add(Objects.requireNonNull(refreshTokenArgumentResolver));
    }

    @Override
    public void addInterceptors(@NonNull InterceptorRegistry registry) {
        registry.addInterceptor(Objects.requireNonNull(jwtBlacklistInterceptor))
                .addPathPatterns("/**")
                .excludePathPatterns(
                        // 인증 관련: 토큰을 발급/검증하는 경로 자체는 토큰 필요 없음
                        "/api/auth/**",            // [추가] 실제 AuthController 매핑(/api/auth/login, /signup, /profile, /logout, /reissue 등)
                        "/api/v1/auth/**",
                        "/api/v1/email/**",
                        "/oauth2/**",              // [추가] Spring Security OAuth2 시작 경로
                        "/login/oauth2/**",        // [추가] OAuth provider 콜백 경로
                        // Swagger / 문서
                        "/swagger-ui/**",
                        "/v3/api-docs/**",
                        "/swagger-resources/**",
                        "/webjars/**",
                        // 도메인 API: SecurityConfig에서 permitAll 처리되는 경로들
                        "/api/v1/reconstruction/**",
                        "/outputs/**",
                        // 정적 리소스 / 시스템 경로
                        "/favicon.ico",            // [추가] 브라우저가 자동으로 요청
                        "/error",                  // [추가] Spring 기본 에러 페이지
                        "/actuator/**"             // [추가] 헬스체크 등
                );
    }

    @Override
    public void addCorsMappings(@NonNull CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
