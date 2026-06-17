package com.youthfi.auth.domain.auth.application.dto.response;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

@DisplayName("LoginResponse 테스트")
class LoginResponseTest {

    @Test
    @DisplayName("유효한 LoginResponse 생성")
    void createValidLoginResponse() {
        // given
        String accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";
        String refreshToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";
        String name = "김원준"; // ✅ 이름 추가

        // when
        LoginResponse response = new LoginResponse(accessToken, refreshToken, name);

        // then
        assertNotNull(response);
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
        assertEquals(name, response.name()); // ✅ 이름 검증 추가
    }

    @Test
    @DisplayName("null 토큰 및 이름으로 LoginResponse 생성")
    void createLoginResponseWithNullValues() {
        // when
        LoginResponse response = new LoginResponse(null, null, null);

        // then
        assertNotNull(response);
        assertNull(response.accessToken());
        assertNull(response.refreshToken());
        assertNull(response.name()); // ✅ 이름 null 체크 추가
    }

    @Test
    @DisplayName("빈 문자열로 LoginResponse 생성")
    void createLoginResponseWithEmptyValues() {
        // given
        String accessToken = "";
        String refreshToken = "";
        String name = "";

        // when
        LoginResponse response = new LoginResponse(accessToken, refreshToken, name);

        // then
        assertNotNull(response);
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
        assertEquals(name, response.name());
    }

    @Test
    @DisplayName("LoginResponse equals 테스트")
    void testLoginResponseEquals() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        String name = "김원준";
        
        LoginResponse response1 = new LoginResponse(accessToken, refreshToken, name);
        LoginResponse response2 = new LoginResponse(accessToken, refreshToken, name);
        LoginResponse response3 = new LoginResponse("different.token", refreshToken, name);
        LoginResponse response4 = new LoginResponse(accessToken, refreshToken, "다른이름");

        // when & then
        assertEquals(response1, response2);
        assertNotEquals(response1, response3);
        assertNotEquals(response1, response4); // ✅ 이름이 다르면 다른 객체여야 함
    }

    @Test
    @DisplayName("LoginResponse toString 테스트")
    void testLoginResponseToString() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        String name = "김원준";
        LoginResponse response = new LoginResponse(accessToken, refreshToken, name);

        // when
        String toString = response.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains("LoginResponse"));
        assertTrue(toString.contains(accessToken));
        assertTrue(toString.contains(refreshToken));
        assertTrue(toString.contains(name)); // ✅ toString에 이름이 포함되는지 확인
    }

    @Test
    @DisplayName("LoginResponse record 특성 테스트")
    void testLoginResponseRecordCharacteristics() {
        // given
        String accessToken = "access.token";
        String refreshToken = "refresh.token";
        String name = "김원준";
        LoginResponse response = new LoginResponse(accessToken, refreshToken, name);

        // when & then
        assertNotNull(response);
        
        // Record의 컴포넌트 접근
        assertEquals(accessToken, response.accessToken());
        assertEquals(refreshToken, response.refreshToken());
        assertEquals(name, response.name()); // ✅ 추가된 필드 접근 확인
        
        assertTrue(LoginResponse.class.isRecord());
    }
}