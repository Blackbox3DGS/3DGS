package com.youthfi.auth.domain.email.application.usecase;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import org.mockito.junit.jupiter.MockitoExtension;

import com.youthfi.auth.domain.email.application.dto.request.VerifyEmailRequest;
import com.youthfi.auth.domain.email.application.dto.response.EmailVerificationResponse;
import com.youthfi.auth.domain.email.domain.service.EmailService;
import com.youthfi.auth.domain.email.domain.service.EmailVerificationService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.EmailErrorStatus;

@ExtendWith(MockitoExtension.class)
@DisplayName("VerifyEmailUseCase 테스트")
@SuppressWarnings("null") // Mockito 매처(anyString 등)와 @NonNull 간의 충돌 경고 무시
class VerifyEmailUseCaseTest {

    @Mock
    private EmailService emailService;

    @Mock
    private EmailVerificationService emailVerificationService;

    @InjectMocks
    private VerifyEmailUseCase verifyEmailUseCase;

    private VerifyEmailRequest validRequest;
    private final String VALID_EMAIL = "test@example.com";
    private final String VALID_CODE = "123456";
    private final long VERIFICATION_TTL_SECONDS = 1800L;

    @BeforeEach
    void setUp() {
        validRequest = new VerifyEmailRequest(VALID_EMAIL, VALID_CODE);
    }

    @Test
    @DisplayName("이메일 인증 검증 성공")
    void verifyEmail_Success() {
        // given
        when(emailService.verifySignupCode(VALID_EMAIL, VALID_CODE)).thenReturn(true);
        doNothing().when(emailVerificationService).markEmailAsVerified(anyString(), anyLong());

        // when
        EmailVerificationResponse response = verifyEmailUseCase.verifyEmail(validRequest);

        // then
        assertNotNull(response);
        assertTrue(response.verified());
        assertEquals(VERIFICATION_TTL_SECONDS, response.expiresInSec());

        verify(emailService, times(1)).verifySignupCode(VALID_EMAIL, VALID_CODE);
        verify(emailVerificationService, times(1)).markEmailAsVerified(VALID_EMAIL, VERIFICATION_TTL_SECONDS);
    }

    @Test
    @DisplayName("인증 코드 검증 실패 시 EMAIL_INVALID_TOKEN 예외 발생")
    void verifyEmail_InvalidCode_ThrowsException() {
        // given
        when(emailService.verifySignupCode(VALID_EMAIL, VALID_CODE))
                .thenThrow(new IllegalArgumentException("유효하지 않은 인증 코드입니다."));

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            verifyEmailUseCase.verifyEmail(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_INVALID_TOKEN.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).verifySignupCode(VALID_EMAIL, VALID_CODE);
        verify(emailVerificationService, never()).markEmailAsVerified(anyString(), anyLong());
    }

    @Test
    @DisplayName("인증 코드가 false 반환 시 EMAIL_INVALID_TOKEN 예외 발생")
    void verifyEmail_CodeValidationFailed_ThrowsException() {
        // given
        when(emailService.verifySignupCode(VALID_EMAIL, VALID_CODE)).thenReturn(false);

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            verifyEmailUseCase.verifyEmail(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_INVALID_TOKEN.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).verifySignupCode(VALID_EMAIL, VALID_CODE);
        verify(emailVerificationService, never()).markEmailAsVerified(anyString(), anyLong());
    }

    @Test
    @DisplayName("이메일 인증 상태 저장 실패 시 EMAIL_VERIFICATION_FAILED 예외 발생")
    void verifyEmail_VerificationServiceFailed_ThrowsException() {
        // given
        when(emailService.verifySignupCode(VALID_EMAIL, VALID_CODE)).thenReturn(true);
        doThrow(new RuntimeException("Redis 저장 실패"))
                .when(emailVerificationService).markEmailAsVerified(anyString(), anyLong());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            verifyEmailUseCase.verifyEmail(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_VERIFICATION_FAILED.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).verifySignupCode(VALID_EMAIL, VALID_CODE);
        verify(emailVerificationService, times(1)).markEmailAsVerified(VALID_EMAIL, VERIFICATION_TTL_SECONDS);
    }

    @Test
    @DisplayName("기타 예외 발생 시 EMAIL_VERIFICATION_FAILED 예외 발생")
    void verifyEmail_OtherException_ThrowsException() {
        // given
        when(emailService.verifySignupCode(VALID_EMAIL, VALID_CODE))
                .thenThrow(new RuntimeException("알 수 없는 오류"));

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            verifyEmailUseCase.verifyEmail(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_VERIFICATION_FAILED.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).verifySignupCode(VALID_EMAIL, VALID_CODE);
        verify(emailVerificationService, never()).markEmailAsVerified(anyString(), anyLong());
    }

    @Test
    @DisplayName("다양한 인증 코드로 테스트")
    void verifyEmail_DifferentCodes() {
        // given
        String[] testCodes = {"123456", "654321", "789012"};
        String[] testEmails = {"test1@example.com", "test2@example.com", "test3@example.com"};

        // Mockito anyString() 대신 실제 값으로 맵핑하여 정확도 향상
        for (int i = 0; i < testCodes.length; i++) {
            when(emailService.verifySignupCode(testEmails[i], testCodes[i])).thenReturn(true);
            doNothing().when(emailVerificationService).markEmailAsVerified(testEmails[i], VERIFICATION_TTL_SECONDS);
        }

        // when & then
        for (int i = 0; i < testCodes.length; i++) {
            VerifyEmailRequest request = new VerifyEmailRequest(testEmails[i], testCodes[i]);
            
            EmailVerificationResponse response = verifyEmailUseCase.verifyEmail(request);
            
            assertNotNull(response);
            assertTrue(response.verified());
            assertEquals(VERIFICATION_TTL_SECONDS, response.expiresInSec());
            
            // 검증 시에도 실제 값으로 호출되었는지 꼼꼼하게 검증
            verify(emailService, times(1)).verifySignupCode(testEmails[i], testCodes[i]);
            verify(emailVerificationService, times(1)).markEmailAsVerified(testEmails[i], VERIFICATION_TTL_SECONDS);
        }
    }

    @Test
    @DisplayName("빈 이메일로 테스트")
    void verifyEmail_EmptyEmail() {
        // given
        VerifyEmailRequest emptyEmailRequest = new VerifyEmailRequest("", VALID_CODE);

        // when & then
        assertThrows(Exception.class, () -> {
            verifyEmailUseCase.verifyEmail(emptyEmailRequest);
        });
    }

    @Test
    @DisplayName("빈 인증 코드로 테스트")
    void verifyEmail_EmptyCode() {
        // given
        VerifyEmailRequest emptyCodeRequest = new VerifyEmailRequest(VALID_EMAIL, "");

        // when & then
        assertThrows(Exception.class, () -> {
            verifyEmailUseCase.verifyEmail(emptyCodeRequest);
        });
    }
}