package com.youthfi.auth.domain.auth.application.service;

import com.youthfi.auth.domain.auth.application.dto.oauth.GoogleResponse; 
import com.youthfi.auth.domain.auth.application.dto.oauth.NaverResponse;
import com.youthfi.auth.domain.auth.application.dto.oauth.KakaoResponse; // 👈 1. 카카오 응답 클래스 임포트 추가!
import com.youthfi.auth.domain.auth.application.dto.oauth.OAuth2Response;
import com.youthfi.auth.domain.auth.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

import java.util.Collections;

@Slf4j
@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService extends DefaultOAuth2UserService {

    private final UserService userService;

    @Override
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        OAuth2User oAuth2User = super.loadUser(userRequest);

        String registrationId = userRequest.getClientRegistration().getRegistrationId();
        
        // 💡 핵심: 구글은 "sub", 네이버는 "response", 카카오는 "id"를 식별자로 씁니다. 이걸 자동으로 가져오게 합니다.
        String userNameAttributeName = userRequest.getClientRegistration()
                .getProviderDetails().getUserInfoEndpoint().getUserNameAttributeName();

        OAuth2Response oAuth2Response = null;

        // 2. 소셜 서비스별 분기 처리
        if (registrationId.equals("naver")) {
            oAuth2Response = new NaverResponse(oAuth2User.getAttributes());
        } else if (registrationId.equals("google")) {
            oAuth2Response = new GoogleResponse(oAuth2User.getAttributes());
        } else if (registrationId.equals("kakao")) {
            // 👈 3. 카카오 조건 추가!
            oAuth2Response = new KakaoResponse(oAuth2User.getAttributes());
        }

        if (oAuth2Response == null) return null;

        // DB에 유저 저장 또는 업데이트
        String username = oAuth2Response.getProvider() + " " + oAuth2Response.getProviderId();
        userService.registerOrUpdateSocialUser(
            username, 
            oAuth2Response.getEmail(), 
            oAuth2Response.getName()
        );

        // 마지막 리턴에서 "response" 대신 유동적인 식별자 키를 넣어줍니다. (401 에러 해결!)
        return new DefaultOAuth2User(
                Collections.emptyList(),
                oAuth2User.getAttributes(),
                userNameAttributeName 
        );
    }
}