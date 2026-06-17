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

@DisplayName("SignUpRequest 테스트")
class SignUpRequestTest {

    private final ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
    private final Validator validator = factory.getValidator();

    @Test
    @DisplayName("유효한 SignUpRequest 생성")
    void createValidSignUpRequest() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertTrue(violations.isEmpty());
        assertEquals("test@example.com", request.email());
        assertEquals("testuser", request.userId());
        assertEquals("password123", request.password());
        assertEquals("홍길동", request.name());
        assertEquals("1990-01-01", request.birth());
    }

    @Test
    @DisplayName("이메일이 null일 때 검증 실패")
    void createSignUpRequestWithNullEmail() {
        // given
        SignUpRequest request = new SignUpRequest(
                null,
                "testuser",
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("email")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("이메일이 빈 문자열일 때 검증 실패")
    void createSignUpRequestWithEmptyEmail() {
        // given
        SignUpRequest request = new SignUpRequest(
                "",
                "testuser",
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("email")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이메일은 필수입니다")));
    }

    @Test
    @DisplayName("잘못된 이메일 형식일 때 검증 실패")
    void createSignUpRequestWithInvalidEmailFormat() {
        // given
        SignUpRequest request = new SignUpRequest(
                "invalid-email",
                "testuser",
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("email")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("올바른 이메일 형식이 아닙니다")));
    }

    @Test
    @DisplayName("사용자 ID가 null일 때 검증 실패")
    void createSignUpRequestWithNullUserId() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                null,
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("아이디는 필수입니다")));
    }

    @Test
    @DisplayName("사용자 ID가 빈 문자열일 때 검증 실패")
    void createSignUpRequestWithEmptyUserId() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "",
                "password123",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("아이디는 필수입니다")));
    }

    @Test
    @DisplayName("비밀번호가 null일 때 검증 실패")
    void createSignUpRequestWithNullPassword() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                null,
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("비밀번호는 필수입니다")));
    }

    @Test
    @DisplayName("비밀번호가 빈 문자열일 때 검증 실패")
    void createSignUpRequestWithEmptyPassword() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "",
                "홍길동",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("비밀번호는 필수입니다")));
    }

    @Test
    @DisplayName("이름이 null일 때 검증 실패")
    void createSignUpRequestWithNullName() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "password123",
                null,
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("name")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이름은 필수입니다")));
    }

    @Test
    @DisplayName("이름이 빈 문자열일 때 검증 실패")
    void createSignUpRequestWithEmptyName() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "password123",
                "",
                "1990-01-01"
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("name")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("이름은 필수입니다")));
    }

    @Test
    @DisplayName("생년월일이 null일 때 검증 실패")
    void createSignUpRequestWithNullBirth() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "password123",
                "홍길동",
                null
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("birth")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("생년월일은 필수입니다")));
    }

    @Test
    @DisplayName("생년월일이 빈 문자열일 때 검증 실패")
    void createSignUpRequestWithEmptyBirth() {
        // given
        SignUpRequest request = new SignUpRequest(
                "test@example.com",
                "testuser",
                "password123",
                "홍길동",
                ""
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("birth")));
        assertTrue(violations.stream().anyMatch(v -> v.getMessage().contains("생년월일은 필수입니다")));
    }

    @Test
    @DisplayName("모든 필드가 null일 때 검증 실패")
    void createSignUpRequestWithAllNullFields() {
        // given
        SignUpRequest request = new SignUpRequest(
                null,
                null,
                null,
                null,
                null
        );

        // when
        Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

        // then
        assertFalse(violations.isEmpty());
        assertEquals(5, violations.size());
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("email")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("userId")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("password")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("name")));
        assertTrue(violations.stream().anyMatch(v -> v.getPropertyPath().toString().equals("birth")));
    }

    @Test
    @DisplayName("다양한 유효한 이메일 형식 테스트")
    void createSignUpRequestWithVariousValidEmailFormats() {
        String[] validEmails = {
                "user@example.com",
                "test.user@domain.co.kr",
                "admin@youthfi.com",
                "user+tag@example.org",
                "user123@test-domain.com"
        };

        for (String email : validEmails) {
            // given
            SignUpRequest request = new SignUpRequest(
                    email,
                    "testuser",
                    "password123",
                    "홍길동",
                    "1990-01-01"
            );

            // when
            Set<ConstraintViolation<SignUpRequest>> violations = validator.validate(request);

            // then
            assertTrue(violations.isEmpty(), "이메일 형식이 유효해야 함: " + email);
        }
    }
}
