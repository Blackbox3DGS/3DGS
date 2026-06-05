package com.youthfi.auth.domain.auth.application.dto.request;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

@DisplayName("LoginRequest 테스트")
class LoginRequestTest {

    private final ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
    private final Validator validator = factory.getValidator();

    @Test
    @DisplayName("유효한 LoginRequest 생성")
    void createValidLoginRequest() {
        // given
        LoginRequest request = new LoginRequest(
                "testuser",
                "password123"
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertTrue(violations.isEmpty());
        assertEquals("testuser", request.userId());
        assertEquals("password123", request.password());
    }

    @Test
    @DisplayName("사용자 ID가 null일 때 검증 실패")
    void createLoginRequestWithNullUserId() {
        // given
        LoginRequest request = new LoginRequest(
                null,
                "password123"
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("사용자 ID는 필수입니다")));
    }

    @Test
    @DisplayName("사용자 ID가 빈 문자열일 때 검증 실패")
    void createLoginRequestWithEmptyUserId() {
        // given
        LoginRequest request = new LoginRequest(
                "",
                "password123"
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("사용자 ID는 필수입니다")));
    }

    @Test
    @DisplayName("사용자 ID가 공백만 있을 때 검증 실패")
    void createLoginRequestWithBlankUserId() {
        // given
        LoginRequest request = new LoginRequest(
                "   ",
                "password123"
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("사용자 ID는 필수입니다")));
    }

    @Test
    @DisplayName("비밀번호가 null일 때 검증 실패")
    void createLoginRequestWithNullPassword() {
        // given
        LoginRequest request = new LoginRequest(
                "testuser",
                null
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("비밀번호는 필수입니다")));
    }

    @Test
    @DisplayName("비밀번호가 빈 문자열일 때 검증 실패")
    void createLoginRequestWithEmptyPassword() {
        // given
        LoginRequest request = new LoginRequest(
                "testuser",
                ""
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("비밀번호는 필수입니다")));
    }

    @Test
    @DisplayName("비밀번호가 공백만 있을 때 검증 실패")
    void createLoginRequestWithBlankPassword() {
        // given
        LoginRequest request = new LoginRequest(
                "testuser",
                "   "
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("비밀번호는 필수입니다")));
    }

    @Test
    @DisplayName("모든 필드가 null일 때 검증 실패")
    void createLoginRequestWithAllNullFields() {
        // given
        LoginRequest request = new LoginRequest(
                null,
                null
        );

        // when
        Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertEquals(2, violations.size());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
    }

    @Test
    @DisplayName("다양한 유효한 사용자 ID 형식 테스트")
    void createLoginRequestWithVariousValidUserIdFormats() {
        String[] validUserIds = {
                "testuser",
                "user123",
                "admin",
                "test_user",
                "user-123",
                "test.user",
                "user@123",
                "123user"
        };

        for (String userId : validUserIds) {
            // given
            LoginRequest request = new LoginRequest(
                    userId,
                    "password123"
            );

            // when
            Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

            // then
            assertTrue(violations.isEmpty(), "사용자 ID가 유효해야 함: " + userId);
        }
    }

    @Test
    @DisplayName("다양한 유효한 비밀번호 형식 테스트")
    void createLoginRequestWithVariousValidPasswordFormats() {
        String[] validPasswords = {
                "password123",
                "Password123!",
                "12345678",
                "abcdefgh",
                "P@ssw0rd",
                "verylongpassword123456789",
                "short1"
        };

        for (String password : validPasswords) {
            // given
            LoginRequest request = new LoginRequest(
                    "testuser",
                    password
            );

            // when
            Set<ConstraintViolation<LoginRequest>> violations = validator.validate(request);

            // then
            assertTrue(violations.isEmpty(), "비밀번호가 유효해야 함: " + password);
        }
    }
}
