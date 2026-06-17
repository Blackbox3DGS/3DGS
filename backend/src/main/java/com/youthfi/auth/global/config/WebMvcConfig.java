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
                        "/api/v1/auth/**", 
                        "/api/v1/email/**", 
                        "/swagger-ui/**", 
                        "/v3/api-docs/**",
                        "/api/v1/reconstruction/**", // 👈 /v1 추가
                        "/outputs/**"
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