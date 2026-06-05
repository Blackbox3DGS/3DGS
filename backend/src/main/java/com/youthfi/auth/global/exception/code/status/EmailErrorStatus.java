package com.youthfi.auth.global.exception.code.status;

import org.springframework.http.HttpStatus;

import com.youthfi.auth.global.exception.code.BaseCode;
import com.youthfi.auth.global.exception.code.BaseCodeInterface;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum EmailErrorStatus implements BaseCodeInterface {
    
    // 이메일 발송 관련
    EMAIL_SEND_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "EMAIL500", "이메일 발송에 실패했습니다."),
    EMAIL_COOLDOWN_ACTIVE(HttpStatus.TOO_MANY_REQUESTS, "EMAIL429", "이메일 발송 쿨다운 중입니다. 잠시 후 다시 시도해주세요."),
    EMAIL_DAILY_LIMIT_EXCEEDED(HttpStatus.TOO_MANY_REQUESTS, "EMAIL429", "일일 이메일 발송 횟수를 초과했습니다."),
    
    // 이메일 인증 관련
    EMAIL_INVALID_TOKEN(HttpStatus.BAD_REQUEST, "EMAIL400", "유효하지 않은 인증 토큰입니다."),
    EMAIL_VERIFICATION_FAILED(HttpStatus.BAD_REQUEST, "EMAIL400", "이메일 인증에 실패했습니다."),
    EMAIL_ALREADY_VERIFIED(HttpStatus.BAD_REQUEST, "EMAIL400", "이미 인증된 이메일입니다."),
    EMAIL_NOT_VERIFIED(HttpStatus.BAD_REQUEST, "EMAIL400", "이메일 인증이 필요합니다."),
    
    // 이메일 형식 관련
    EMAIL_INVALID_FORMAT(HttpStatus.BAD_REQUEST, "EMAIL400", "올바른 이메일 형식이 아닙니다."),
    EMAIL_ALREADY_EXISTS(HttpStatus.BAD_REQUEST, "EMAIL400", "이미 사용 중인 이메일입니다.");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;

    @Override
    public BaseCode getCode() {
        return BaseCode.builder()
                .httpStatus(httpStatus)
                .isSuccess(false)
                .code(code)
                .message(message)
                .build();
    }
}
