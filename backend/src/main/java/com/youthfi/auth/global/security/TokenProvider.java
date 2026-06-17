package com.youthfi.auth.global.security;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.Date;
import java.util.Optional;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;

import com.youthfi.auth.global.exception.RestApiException;
import static com.youthfi.auth.global.exception.code.status.AuthErrorStatus.UNSUPPORTED_JWT;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Header;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class TokenProvider {

    private final JwtProperties jwtProperties;

    private static final String ACCESS_TOKEN_SUBJECT = "AccessToken";
    private static final String REFRESH_TOKEN_SUBJECT = "RefreshToken";
    private static final String EMAIL_VERIFICATION_SUBJECT = "EmailVerification";
    private static final String TOKEN_HEADER = "Authorization";
    private static final String BEARER = "Bearer ";
    private static final String ID_CLAIM = "id";
    private static final String TYPE_CLAIM = "type";


    public String createAccessToken(String id) {
        Date now = new Date();
        return Jwts.builder()
                .setHeaderParam(Header.TYPE, Header.JWT_TYPE)
                .setIssuedAt(now)
                .setExpiration(new Date(System.currentTimeMillis() + jwtProperties.getAccessTokenExpirationMs()))
                .setSubject(ACCESS_TOKEN_SUBJECT)
                .claim(ID_CLAIM, id)
                .signWith(Keys.hmacShaKeyFor(jwtProperties.getKey().getBytes(StandardCharsets.UTF_8)), SignatureAlgorithm.HS256)
                .compact();
    }

    public String createRefreshToken(String id) {
        Date now = new Date();
        return Jwts.builder()
                .setHeaderParam(Header.TYPE, Header.JWT_TYPE)
                .setIssuedAt(now)
                .setExpiration(new Date(System.currentTimeMillis() + jwtProperties.getRefreshTokenExpirationMs()))
                .setSubject(REFRESH_TOKEN_SUBJECT)
                .claim(ID_CLAIM, id)
                .signWith(Keys.hmacShaKeyFor(jwtProperties.getKey().getBytes(StandardCharsets.UTF_8)), SignatureAlgorithm.HS256)
                .compact();
    }

    public Boolean validateToken(String jwtToken) {
        try {
            Jwts.parserBuilder().setSigningKey(Keys.hmacShaKeyFor(jwtProperties.getKey().getBytes(StandardCharsets.UTF_8)))
                    .build()
                    .parseClaimsJws(jwtToken);  // Decode
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public Authentication getAuthentication(String token) {
        Claims claims = getClaims(token);
        // 권한 없이 인증된 사용자로만 처리
        return new UsernamePasswordAuthenticationToken(claims.get(ID_CLAIM, String.class), "", Collections.emptyList());
    }

    public Optional<String> getId(String token) {
        try {
            return Optional.ofNullable(getClaims(token).get(ID_CLAIM, String.class));
        } catch (Exception e) {
            return Optional.empty();
        }
    }



    public Optional<String> getToken(HttpServletRequest request) {
        return Optional.ofNullable(request.getHeader(TOKEN_HEADER))
                .filter(token -> token.startsWith(BEARER))
                .map(token -> token.replace(BEARER, ""));
    }

    private Claims getClaims(String token) {
        return Jwts.parserBuilder().setSigningKey(Keys.hmacShaKeyFor(jwtProperties.getKey().getBytes(StandardCharsets.UTF_8)))
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    public Optional<Date> getExpiration(String token) {
        try {
            return Optional.ofNullable(getClaims(token).getExpiration());
        } catch (Exception e) {
            return Optional.empty();
        }
    }

    public Optional<Duration> getRemainingDuration(String token) {
        return getExpiration(token)
                .map(date -> Duration.between(Instant.now(), date.toInstant()));
    }

    public boolean isAccessToken(String token) {
        try {
            String subject = getClaims(token).getSubject();
            return ACCESS_TOKEN_SUBJECT.equals(subject);
        } catch (Exception e) {
            throw new RestApiException(UNSUPPORTED_JWT);
        }
    }

    /**
     * 이메일 인증용 JWT 토큰 생성
     * @param email 인증할 이메일
     * @param type 토큰 타입 ("signup", "reset" 등)
     * @return JWT 토큰
     */
    public String createEmailVerificationToken(String email, String type) {
        Date now = new Date();
        return Jwts.builder()
                .setHeaderParam(Header.TYPE, Header.JWT_TYPE)
                .setIssuedAt(now)
                .setExpiration(new Date(System.currentTimeMillis() + jwtProperties.getVerificationExpirationMs()))
                .setSubject(EMAIL_VERIFICATION_SUBJECT)
                .claim(ID_CLAIM, email)  // 이메일을 ID 클레임에 저장
                .claim(TYPE_CLAIM, type)  // 토큰 타입 저장
                .signWith(Keys.hmacShaKeyFor(jwtProperties.getKey().getBytes(StandardCharsets.UTF_8)), SignatureAlgorithm.HS256)
                .compact();
    }

    /**
     * 이메일 인증용 JWT 토큰 검증
     * @param token 검증할 토큰
     * @param expectedType 예상하는 토큰 타입
     * @return 검증 성공 여부
     */
    public boolean validateEmailVerificationToken(String token, String expectedType) {
        try {
            Claims claims = getClaims(token);
            String subject = claims.getSubject();
            String type = claims.get(TYPE_CLAIM, String.class);
            
            return EMAIL_VERIFICATION_SUBJECT.equals(subject) && expectedType.equals(type);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 이메일 인증용 JWT 토큰에서 이메일 추출
     * @param token JWT 토큰
     * @return 이메일 주소
     */
    public Optional<String> getEmailFromVerificationToken(String token) {
        try {
            return Optional.ofNullable(getClaims(token).get(ID_CLAIM, String.class));
        } catch (Exception e) {
            return Optional.empty();
        }
    }
}