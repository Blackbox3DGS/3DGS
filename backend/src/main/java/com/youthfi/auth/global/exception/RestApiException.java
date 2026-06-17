package com.youthfi.auth.global.exception;

import com.youthfi.auth.global.exception.code.BaseCode;
import com.youthfi.auth.global.exception.code.BaseCodeInterface;
import lombok.AllArgsConstructor;

@AllArgsConstructor
public class RestApiException extends RuntimeException {

    private final BaseCodeInterface errorCode;

    public BaseCode getErrorCode() {
        return this.errorCode.getCode();
    }

}
