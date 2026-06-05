package com.youthfi.auth.domain.auth.application.dto.oauth;

public interface OAuth2Response {
    // 제공자 (naver, kakao 등)
    String getProvider();
    
    // 제공자에서 발급해주는 유니크한 아이디
    String getProviderId();
    
    // 이메일
    String getEmail();
    
    // 사용자 실명 (또는 닉네임)
    String getName();
}