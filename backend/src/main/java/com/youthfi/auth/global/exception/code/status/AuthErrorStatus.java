package com.youthfi.auth.global.exception.code.status;

import org.springframework.http.HttpStatus;

import com.youthfi.auth.global.exception.code.BaseCode;
import com.youthfi.auth.global.exception.code.BaseCodeInterface;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum AuthErrorStatus implements BaseCodeInterface {

    EMPTY_JWT(HttpStatus.UNAUTHORIZED, "AUTH001", "JWT가 없습니다."),
    EXPIRED_MEMBER_JWT(HttpStatus.UNAUTHORIZED, "AUTH002", "만료된 JWT입니다."),
    UNSUPPORTED_JWT(HttpStatus.UNAUTHORIZED, "AUTH003", "지원하지 않는 JWT입니다."),

    INVALID_ID_TOKEN(HttpStatus.BAD_REQUEST, "AUTH004", "유효하지 않은 ID TOKEN입니다."),
    EXPIRED_REFRESH_TOKEN(HttpStatus.BAD_REQUEST, "AUTH005", "만료된 REFRESH TOKEN입니다."),
    INVALID_ACCESS_TOKEN(HttpStatus.BAD_REQUEST, "AUTH006", "유효하지 않은 ACCESS TOKEN입니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.BAD_REQUEST, "AUTH007", "유효하지 않은 REFRESH TOKEN입니다."),
    LOGIN_ERROR(HttpStatus.BAD_REQUEST, "AUTH008", "잘못된 아이디 혹은 비밀번호입니다."),
    ALREADY_REGISTERED_EMAIL(HttpStatus.CONFLICT, "AUTH009", "이미 가입된 이메일입니다."),
    ALREADY_REGISTERED_USER_ID(HttpStatus.CONFLICT, "AUTH010", "이미 사용 중인 아이디입니다."),

    // Social Login
    SOCIAL_TOKEN_EXCHANGE_FAILED(HttpStatus.BAD_GATEWAY, "AUTH011", "소셜 토큰 교환에 실패했습니다."),
    SOCIAL_USERINFO_FAILED(HttpStatus.BAD_GATEWAY, "AUTH012", "소셜 사용자 정보 조회에 실패했습니다."),
    SOCIAL_UNSUPPORTED_PROVIDER(HttpStatus.BAD_REQUEST, "AUTH013", "지원하지 않는 소셜 공급자입니다."),
    OAUTH2_AUTHENTICATION_FAILED(HttpStatus.BAD_REQUEST, "AUTH014", "OAuth2 인증에 실패했습니다.");

    private final HttpStatus httpStatus;
    private final boolean isSuccess = false;
    private final String code;
    private final String message;

    @Override
    public BaseCode getCode() {
        return BaseCode.builder()
                .httpStatus(httpStatus)
                .isSuccess(isSuccess)
                .code(code)
                .message(message)
                .build();
    }

}
