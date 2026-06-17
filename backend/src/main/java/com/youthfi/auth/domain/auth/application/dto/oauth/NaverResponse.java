package com.youthfi.auth.domain.auth.application.dto.oauth;

import java.util.Map;

public class NaverResponse implements OAuth2Response {

    private final Map<String, Object> attribute;

    @SuppressWarnings("unchecked")
    public NaverResponse(Map<String, Object> attribute) {
        // 네이버가 주는 JSON 데이터에서 "response" 키 안에 있는 알맹이만 쏙 뽑아옵니다.
        this.attribute = (Map<String, Object>) attribute.get("response");
    }

    @Override
    public String getProvider() {
        return "naver";
    }

    @Override
    public String getProviderId() {
        // 네이버에서 제공하는 고유 ID 값입니다.
        return attribute.get("id").toString();
    }

    @Override
    public String getEmail() {
        // 사용자의 이메일 정보입니다.
        return attribute.get("email").toString();
    }

    @Override
    public String getName() {
        // 사용자의 이름 정보입니다.
        return attribute.get("name").toString();
    }
}