package com.youthfi.auth.domain.email.application.dto.response;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

@DisplayName("EmailVerificationResponse 테스트")
class EmailVerificationResponseTest {

    @Test
    @DisplayName("인증 성공 응답 생성")
    void createSuccessResponse_Success() {
        // given
        boolean verified = true;
        long expiresInSec = 1800L;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, expiresInSec);

        // then
        assertNotNull(response);
        assertTrue(response.verified());
        assertEquals(expiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("인증 실패 응답 생성")
    void createFailureResponse_Success() {
        // given
        boolean verified = false;
        long expiresInSec = 0L;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, expiresInSec);

        // then
        assertNotNull(response);
        assertFalse(response.verified());
        assertEquals(expiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("다양한 만료 시간으로 응답 생성")
    void createResponseWithVariousExpirationTimes_Success() {
        // given
        long[] expirationTimes = {
                0L,
                60L,        // 1분
                300L,       // 5분
                1800L,      // 30분
                3600L,      // 1시간
                86400L,     // 24시간
                604800L,    // 7일
                2592000L    // 30일
        };

        // when & then
        for (long expirationTime : expirationTimes) {
            EmailVerificationResponse response = new EmailVerificationResponse(true, expirationTime);
            
            assertNotNull(response);
            assertTrue(response.verified());
            assertEquals(expirationTime, response.expiresInSec());
        }
    }

    @Test
    @DisplayName("음수 만료 시간으로 응답 생성")
    void createResponseWithNegativeExpirationTime_Success() {
        // given
        boolean verified = true;
        long negativeExpiresInSec = -100L;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, negativeExpiresInSec);

        // then
        assertNotNull(response);
        assertTrue(response.verified());
        assertEquals(negativeExpiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("Record equals 및 hashCode 테스트")
    void recordEqualsAndHashCode() {
        // given
        boolean verified = true;
        long expiresInSec = 1800L;
        
        EmailVerificationResponse response1 = new EmailVerificationResponse(verified, expiresInSec);
        EmailVerificationResponse response2 = new EmailVerificationResponse(verified, expiresInSec);
        EmailVerificationResponse response3 = new EmailVerificationResponse(false, expiresInSec);
        EmailVerificationResponse response4 = new EmailVerificationResponse(verified, 3600L);

        // when & then
        assertEquals(response1, response2);
        assertNotEquals(response1, response3);
        assertNotEquals(response1, response4);
        assertEquals(response1.hashCode(), response2.hashCode());
        assertNotEquals(response1.hashCode(), response3.hashCode());
        assertNotEquals(response1.hashCode(), response4.hashCode());
    }

    @Test
    @DisplayName("Record toString 테스트")
    void recordToString() {
        // given
        boolean verified = true;
        long expiresInSec = 1800L;
        EmailVerificationResponse response = new EmailVerificationResponse(verified, expiresInSec);

        // when
        String toString = response.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains("true"));
        assertTrue(toString.contains("1800"));
    }

    @ParameterizedTest
    @ValueSource(booleans = {true, false})
    @DisplayName("다양한 verified 값으로 테스트")
    void createResponseWithVariousVerifiedValues(boolean verified) {
        // given
        long expiresInSec = 1800L;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, expiresInSec);

        // then
        assertNotNull(response);
        assertEquals(verified, response.verified());
        assertEquals(expiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("최대값 만료 시간으로 응답 생성")
    void createResponseWithMaxExpirationTime_Success() {
        // given
        boolean verified = true;
        long maxExpiresInSec = Long.MAX_VALUE;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, maxExpiresInSec);

        // then
        assertNotNull(response);
        assertTrue(response.verified());
        assertEquals(maxExpiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("최소값 만료 시간으로 응답 생성")
    void createResponseWithMinExpirationTime_Success() {
        // given
        boolean verified = true;
        long minExpiresInSec = Long.MIN_VALUE;

        // when
        EmailVerificationResponse response = new EmailVerificationResponse(verified, minExpiresInSec);

        // then
        assertNotNull(response);
        assertTrue(response.verified());
        assertEquals(minExpiresInSec, response.expiresInSec());
    }

    @Test
    @DisplayName("실제 사용 시나리오 테스트")
    void createResponseForRealWorldScenarios() {
        // given & when & then
        
        // 시나리오 1: 회원가입 이메일 인증 성공 (30분 TTL)
        EmailVerificationResponse signupSuccess = new EmailVerificationResponse(true, 1800L);
        assertTrue(signupSuccess.verified());
        assertEquals(1800L, signupSuccess.expiresInSec());

        // 시나리오 2: 토큰 만료로 인한 인증 실패
        EmailVerificationResponse tokenExpired = new EmailVerificationResponse(false, 0L);
        assertFalse(tokenExpired.verified());
        assertEquals(0L, tokenExpired.expiresInSec());

        // 시나리오 3: 잘못된 토큰으로 인한 인증 실패
        EmailVerificationResponse invalidToken = new EmailVerificationResponse(false, 0L);
        assertFalse(invalidToken.verified());
        assertEquals(0L, invalidToken.expiresInSec());
    }
}
