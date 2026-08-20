package com.youthfi.auth.global.config.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component; // 1. 이 줄이 추가되어야 합니다.

@Data
@ConfigurationProperties(prefix = "cors")
@Component // 2. 이 어노테이션을 붙여야 스프링이 "아, 이게 그 부품이구나!" 하고 알아챕니다.
public class CorsProperties {
    private String allowedOrigins;
    private String allowedMethods;
    private String allowedHeaders;
    private Long maxAge;
}