package com.youthfi.auth.domain.email.application.dto.request;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

@DisplayName("SendVerificationRequest 테스트")
class SendVerificationRequestTest {

    private final ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
    private final Validator validator = factory.getValidator();

    @Test
    @DisplayName("유효한 이메일 주소로 생성 성공")
    void createWithValidEmail_Success() {
        // given
        String validEmail = "test@example.com";

        // when
        SendVerificationRequest request = new SendVerificationRequest(validEmail);

        // then
        assertNotNull(request);
        assertEquals(validEmail, request.email());
    }

    @Test
    @DisplayName("다양한 유효한 이메일 형식 테스트")
    void createWithVariousValidEmails_Success() {
        // given
        String[] validEmails = {
                "user@example.com",
                "test.user@domain.co.kr",
                "admin@youthfi.com",
                "user+tag@example.org",
                "user123@test-domain.com"
        };

        // when & then
        for (String email : validEmails) {
            SendVerificationRequest request = new SendVerificationRequest(email);
            assertNotNull(request);
            assertEquals(email, request.email());
        }
    }

    @Test
    @DisplayName("빈 문자열 이메일로 생성 시 검증 실패")
    void createWithEmptyEmail_ValidationFails() {
        // given
        String emptyEmail = "";

        // when
        SendVerificationRequest request = new SendVerificationRequest(emptyEmail);
        Set<ConstraintViolation<SendVerificationRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("null 이메일로 생성 시 검증 실패")
    void createWithNullEmail_ValidationFails() {
        // given
        String nullEmail = null;

        // when
        SendVerificationRequest request = new SendVerificationRequest(nullEmail);
        Set<ConstraintViolation<SendVerificationRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "invalid-email",
            "@example.com",
            "user@",
            "user@.com",
            "user..name@example.com",
            "user@example..com",
            "user@example.com.",
            "user name@example.com",
            "user@exam ple.com"
    })
    @DisplayName("잘못된 이메일 형식으로 생성 시 검증 실패")
    void createWithInvalidEmailFormat_ValidationFails(String invalidEmail) {
        // when
        SendVerificationRequest request = new SendVerificationRequest(invalidEmail);
        Set<ConstraintViolation<SendVerificationRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("올바른 이메일 형식이 아닙니다")));
    }

    @Test
    @DisplayName("공백만 있는 이메일로 생성 시 검증 실패")
    void createWithWhitespaceOnlyEmail_ValidationFails() {
        // given
        String whitespaceEmail = "   ";

        // when
        SendVerificationRequest request = new SendVerificationRequest(whitespaceEmail);
        Set<ConstraintViolation<SendVerificationRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("매우 긴 이메일 주소로 생성 시 검증 실패")
    void createWithVeryLongEmail_ValidationFails() {
        // given
        String longEmail = "a".repeat(100) + "@" + "b".repeat(100) + ".com";

        // when
        SendVerificationRequest request = new SendVerificationRequest(longEmail);
        Set<ConstraintViolation<SendVerificationRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("올바른 이메일 형식이 아닙니다")));
    }

    @Test
    @DisplayName("Record equals 및 hashCode 테스트")
    void recordEqualsAndHashCode() {
        // given
        String email = "test@example.com";
        SendVerificationRequest request1 = new SendVerificationRequest(email);
        SendVerificationRequest request2 = new SendVerificationRequest(email);
        SendVerificationRequest request3 = new SendVerificationRequest("different@example.com");

        // when & then
        assertEquals(request1, request2);
        assertNotEquals(request1, request3);
        assertEquals(request1.hashCode(), request2.hashCode());
        assertNotEquals(request1.hashCode(), request3.hashCode());
    }

    @Test
    @DisplayName("Record toString 테스트")
    void recordToString() {
        // given
        String email = "test@example.com";
        SendVerificationRequest request = new SendVerificationRequest(email);

        // when
        String toString = request.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains(email));
    }
}
