package com.youthfi.auth.domain.email.application.usecase;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import static org.mockito.ArgumentMatchers.anyString;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import org.mockito.junit.jupiter.MockitoExtension;

import com.youthfi.auth.domain.email.application.dto.request.SendVerificationRequest;
import com.youthfi.auth.domain.email.domain.service.EmailService;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.EmailErrorStatus;

@ExtendWith(MockitoExtension.class)
@DisplayName("SendEmailVerificationUseCase 테스트")
@SuppressWarnings("null") // Mockito 매처 및 리터럴 사용 시 발생하는 Null type safety 경고 억제
class SendEmailVerificationUseCaseTest {

    @Mock
    private EmailService emailService;

    @InjectMocks
    private SendEmailVerificationUseCase sendEmailVerificationUseCase;

    private SendVerificationRequest validRequest;

    @BeforeEach
    void setUp() {
        validRequest = new SendVerificationRequest("test@example.com");
    }

    @Test
    @DisplayName("이메일 인증 발송 성공")
    void sendVerification_Success() {
        // given
        doNothing().when(emailService).sendVerificationCode(anyString());

        // when & then
        assertDoesNotThrow(() -> {
            sendEmailVerificationUseCase.sendVerification(validRequest);
        });

        verify(emailService, times(1)).sendVerificationCode("test@example.com");
    }

    @Test
    @DisplayName("쿨다운 중일 때 EMAIL_COOLDOWN_ACTIVE 예외 발생")
    void sendVerification_CooldownActive_ThrowsException() {
        // given
        doThrow(new RuntimeException("이메일 발송 쿨다운 중입니다. 잠시 후 다시 시도해주세요."))
                .when(emailService).sendVerificationCode(anyString());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            sendEmailVerificationUseCase.sendVerification(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_COOLDOWN_ACTIVE.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).sendVerificationCode("test@example.com");
    }

    @Test
    @DisplayName("일일 발송 횟수 초과 시 EMAIL_DAILY_LIMIT_EXCEEDED 예외 발생")
    void sendVerification_DailyLimitExceeded_ThrowsException() {
        // given
        doThrow(new RuntimeException("일일 이메일 발송 횟수를 초과했습니다."))
                .when(emailService).sendVerificationCode(anyString());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            sendEmailVerificationUseCase.sendVerification(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_DAILY_LIMIT_EXCEEDED.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).sendVerificationCode("test@example.com");
    }

    @Test
    @DisplayName("이메일 발송 실패 시 EMAIL_SEND_FAILED 예외 발생")
    void sendVerification_EmailSendFailed_ThrowsException() {
        // given
        doThrow(new RuntimeException("이메일 전송에 실패했습니다."))
                .when(emailService).sendVerificationCode(anyString());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            sendEmailVerificationUseCase.sendVerification(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_SEND_FAILED.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).sendVerificationCode("test@example.com");
    }

    @Test
    @DisplayName("기타 예외 발생 시 EMAIL_SEND_FAILED 예외 발생")
    void sendVerification_OtherException_ThrowsException() {
        // given
        doThrow(new IllegalArgumentException("알 수 없는 오류"))
                .when(emailService).sendVerificationCode(anyString());

        // when & then
        RestApiException exception = assertThrows(RestApiException.class, () -> {
            sendEmailVerificationUseCase.sendVerification(validRequest);
        });

        assertEquals(EmailErrorStatus.EMAIL_SEND_FAILED.getCode(), exception.getErrorCode());
        verify(emailService, times(1)).sendVerificationCode("test@example.com");
    }

    @Test
    @DisplayName("다양한 이메일 주소로 테스트")
    void sendVerification_DifferentEmailAddresses() {
        // given
        String[] testEmails = {
                "user@example.com",
                "test.user@domain.co.kr",
                "admin@youthfi.com"
        };

        doNothing().when(emailService).sendVerificationCode(anyString());

        // when & then
        for (String email : testEmails) {
            SendVerificationRequest request = new SendVerificationRequest(email);
            
            assertDoesNotThrow(() -> {
                sendEmailVerificationUseCase.sendVerification(request);
            });
        }

        verify(emailService, times(testEmails.length)).sendVerificationCode(anyString());
    }
}