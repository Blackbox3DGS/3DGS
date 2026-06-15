package com.youthfi.auth.global.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Component
public class JwtProperties {
    @Value("${jwt.key}")
    private String key;

    @Value("${jwt.access.expiration}")
    private Long accessTokenExpirationMs;

    @Value("${jwt.refresh.expiration}")
    private Long refreshTokenExpirationMs;

    @Value("${jwt.verification-expiration-ms:900000}") // 15분 기본값
    private Long verificationExpirationMs;
    
    public String getKey() {
        return key;
    }
    
    public Long getAccessTokenExpirationMs() {
        return accessTokenExpirationMs;
    }
    
    public Long getRefreshTokenExpirationMs() {
        return refreshTokenExpirationMs;
    }
    
    public Long getVerificationExpirationMs() {
        return verificationExpirationMs;
    }
}