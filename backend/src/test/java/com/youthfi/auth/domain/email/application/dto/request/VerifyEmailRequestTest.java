package com.youthfi.auth.domain.email.application.dto.request;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

@DisplayName("VerifyEmailRequest 테스트")
class VerifyEmailRequestTest {

    private final ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
    private final Validator validator = factory.getValidator();

    @Test
    @DisplayName("유효한 이메일과 인증 코드로 생성 성공")
    void createWithValidEmailAndCode_Success() {
        // given
        String validEmail = "test@example.com";
        String validCode = "123456";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(validEmail, validCode);

        // then
        assertNotNull(request);
        assertEquals(validEmail, request.email());
        assertEquals(validCode, request.verificationCode());
    }

    @Test
    @DisplayName("다양한 유효한 이메일과 인증 코드 형식 테스트")
    void createWithVariousValidEmailsAndCodes_Success() {
        // given
        String[] validEmails = {
                "test@example.com",
                "user@domain.co.kr",
                "admin@youthfi.com"
        };
        String[] validCodes = {"123456", "654321", "789012"};

        // when & then
        for (int i = 0; i < validEmails.length; i++) {
            VerifyEmailRequest request = new VerifyEmailRequest(validEmails[i], validCodes[i]);
            assertNotNull(request);
            assertEquals(validEmails[i], request.email());
            assertEquals(validCodes[i], request.verificationCode());
        }
    }

    @Test
    @DisplayName("빈 문자열 이메일로 생성 시 검증 실패")
    void createWithEmptyEmail_ValidationFails() {
        // given
        String emptyEmail = "";
        String validCode = "123456";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(emptyEmail, validCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("null 이메일로 생성 시 검증 실패")
    void createWithNullEmail_ValidationFails() {
        // given
        String nullEmail = null;
        String validCode = "123456";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(nullEmail, validCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("빈 문자열 인증 코드로 생성 시 검증 실패")
    void createWithEmptyCode_ValidationFails() {
        // given
        String validEmail = "test@example.com";
        String emptyCode = "";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(validEmail, emptyCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("인증 코드는 필수입니다")));
    }

    @Test
    @DisplayName("잘못된 이메일 형식으로 생성 시 검증 실패")
    void createWithInvalidEmailFormat_ValidationFails() {
        // given
        String invalidEmail = "invalid-email";
        String validCode = "123456";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(invalidEmail, validCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("올바른 이메일 형식이 아닙니다")));
    }

    @Test
    @DisplayName("6자리가 아닌 인증 코드로 생성 시 검증 실패")
    void createWithInvalidCodeLength_ValidationFails() {
        // given
        String validEmail = "test@example.com";
        String invalidCode = "12345"; // 5자리

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(validEmail, invalidCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("인증 코드는 6자리 숫자여야 합니다")));
    }

    @Test
    @DisplayName("숫자가 아닌 인증 코드로 생성 시 검증 실패")
    void createWithNonNumericCode_ValidationFails() {
        // given
        String validEmail = "test@example.com";
        String invalidCode = "abc123"; // 숫자가 아닌 문자 포함

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(validEmail, invalidCode);
        Set<ConstraintViolation<VerifyEmailRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("인증 코드는 6자리 숫자여야 합니다")));
    }

    @Test
    @DisplayName("Record equals 및 hashCode 테스트")
    void recordEqualsAndHashCode() {
        // given
        String email = "test@example.com";
        String code = "123456";
        VerifyEmailRequest request1 = new VerifyEmailRequest(email, code);
        VerifyEmailRequest request2 = new VerifyEmailRequest(email, code);
        VerifyEmailRequest request3 = new VerifyEmailRequest("different@example.com", code);

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
        String code = "123456";
        VerifyEmailRequest request = new VerifyEmailRequest(email, code);

        // when
        String toString = request.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains(email));
        assertTrue(toString.contains(code));
    }

    @Test
    @DisplayName("유효한 6자리 인증 코드로 생성 시 성공")
    void createWithValidSixDigitCode_Success() {
        // given
        String validEmail = "test@example.com";
        String validCode = "123456";

        // when
        VerifyEmailRequest request = new VerifyEmailRequest(validEmail, validCode);

        // then
        assertNotNull(request);
        assertEquals(validEmail, request.email());
        assertEquals(validCode, request.verificationCode());
    }
}
