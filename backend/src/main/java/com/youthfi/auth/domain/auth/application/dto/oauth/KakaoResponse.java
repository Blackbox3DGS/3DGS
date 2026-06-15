package com.youthfi.auth.domain.auth.application.dto.oauth;

import java.util.Map;

public class KakaoResponse implements OAuth2Response {

    private final Map<String, Object> attribute;
    private final Map<String, Object> kakaoAccount;
    private final Map<String, Object> profile;

    @SuppressWarnings("unchecked")
    public KakaoResponse(Map<String, Object> attribute) {
        this.attribute = attribute;
        // 카카오는 kakao_account 안에 이메일이, 그 안의 profile에 이름이 들어있습니다.
        this.kakaoAccount = (Map<String, Object>) attribute.get("kakao_account");
        this.profile = (Map<String, Object>) kakaoAccount.get("profile");
    }

    @Override
    public String getProvider() {
        return "kakao";
    }

    @Override
    public String getProviderId() {
        return attribute.get("id").toString();
    }

    @Override
    public String getEmail() {
        // 👈 이메일 권한이 없어서 null이 들어오는 경우를 위한 방어 코드!
        if (kakaoAccount == null || kakaoAccount.get("email") == null) {
            return "none"; 
        }
        return kakaoAccount.get("email").toString();
    }

    @Override
    public String getName() {
        // 혹시 몰라 이름(닉네임)도 null 체크를 해둡니다.
        if (profile == null || profile.get("nickname") == null) {
            return "KakaoUser";
        }
        return profile.get("nickname").toString();
    }
}