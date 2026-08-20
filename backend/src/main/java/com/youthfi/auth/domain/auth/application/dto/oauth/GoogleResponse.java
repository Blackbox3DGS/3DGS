package com.youthfi.auth.domain.auth.application.dto.oauth;

import java.util.Map;

public class GoogleResponse implements OAuth2Response {

    private final Map<String, Object> attribute;

    public GoogleResponse(Map<String, Object> attribute) {
        // 구글은 네이버처럼 "response" 주머니가 없고, 
        // 데이터가 최상위에 바로 있어서 그냥 통째로 받으면 됩니다.
        this.attribute = attribute;
    }

    @Override
    public String getProvider() {
        return "google";
    }

    @Override
    public String getProviderId() {
        // 구글의 고유 ID 키값은 "sub"입니다.
        return attribute.get("sub").toString();
    }

    @Override
    public String getEmail() {
        return attribute.get("email").toString();
    }

    @Override
    public String getName() {
        return attribute.get("name").toString();
    }
}