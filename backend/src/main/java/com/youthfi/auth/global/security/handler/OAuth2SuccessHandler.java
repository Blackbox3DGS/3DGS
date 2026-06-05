package com.youthfi.auth.global.security.handler;

import com.youthfi.auth.global.security.TokenProvider;
import com.youthfi.auth.domain.auth.domain.service.RefreshTokenService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.authentication.OAuth2AuthenticationToken;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.authentication.SimpleUrlAuthenticationSuccessHandler;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class OAuth2SuccessHandler extends SimpleUrlAuthenticationSuccessHandler {

    private final TokenProvider tokenProvider;
    private final RefreshTokenService refreshTokenService;

    @Override
    @SuppressWarnings("unchecked")
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response, Authentication authentication) throws IOException {
        
        // 1. 현재 로그인한 소셜 플랫폼이 어디인지 알아냅니다 (naver, google, kakao)
        OAuth2AuthenticationToken oauthToken = (OAuth2AuthenticationToken) authentication;
        String provider = oauthToken.getAuthorizedClientRegistrationId();
        
        OAuth2User oAuth2User = oauthToken.getPrincipal();
        String providerId = "";

        // 2. 소셜 플랫폼에 따라 다르게 ID를 꺼내옵니다.
        if ("naver".equals(provider)) {
            Map<String, Object> attributes = (Map<String, Object>) oAuth2User.getAttributes().get("response");
            if (attributes == null || attributes.get("id") == null) {
                log.error("네이버로부터 사용자 정보를 가져오지 못했습니다.");
                response.sendError(HttpServletResponse.SC_BAD_REQUEST, "Invalid OAuth2 response");
                return;
            }
            providerId = attributes.get("id").toString();
            
        } else if ("google".equals(provider)) {
            // 구글은 response 주머니 없이 바로 'sub'라는 키를 씁니다.
            if (oAuth2User.getAttributes().get("sub") == null) {
                log.error("구글로부터 사용자 정보를 가져오지 못했습니다.");
                response.sendError(HttpServletResponse.SC_BAD_REQUEST, "Invalid OAuth2 response");
                return;
            }
            providerId = oAuth2User.getAttributes().get("sub").toString();
            
        } else if ("kakao".equals(provider)) {
            // 👈 카카오 로직 추가: 카카오는 최상단에 'id'를 씁니다.
            if (oAuth2User.getAttributes().get("id") == null) {
                log.error("카카오로부터 사용자 정보를 가져오지 못했습니다.");
                response.sendError(HttpServletResponse.SC_BAD_REQUEST, "Invalid OAuth2 response");
                return;
            }
            providerId = oAuth2User.getAttributes().get("id").toString();
        }

        // 3. 통합 userId 생성 (예: naver 1234, google 5678, kakao 9012)
        String userId = provider + " " + providerId;
        log.info("OAuth2 로그인 성공: userId = {}", userId);

        // 4. 토큰 생성 및 저장
        String accessToken = tokenProvider.createAccessToken(userId);
        String refreshToken = tokenProvider.createRefreshToken(userId);

        refreshTokenService.saveRefreshToken(userId, refreshToken, Duration.ofDays(14));

        // 5. 프론트엔드로 리다이렉트
        String targetUrl = UriComponentsBuilder.fromUriString("http://localhost:3000/oauth/callback")
                .queryParam("accessToken", accessToken)
                .queryParam("refreshToken", refreshToken)
                .build().toUriString();

        getRedirectStrategy().sendRedirect(request, response, targetUrl);
    }
}