package com.youthfi.auth.global.config;

import java.util.Objects;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.lang.NonNull;
import org.springframework.web.client.RestTemplate;

@Configuration
public class RestTemplateConfig {

    @Bean
    public RestTemplate restTemplate(@NonNull RestTemplateBuilder builder) {
        // 파라미터에 @NonNull을 추가하여 IDE의 경고를 근본적으로 해결했습니다.
        
        RestTemplateBuilder safeBuilder =
                Objects.requireNonNull(builder, "RestTemplateBuilder must not be null");

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        
        // 타임아웃 설정 (밀리초 단위)
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(10000);

        return safeBuilder
                .requestFactory(() -> factory)
                .build();
    }
}