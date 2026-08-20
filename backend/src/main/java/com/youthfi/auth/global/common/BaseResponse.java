package com.youthfi.auth.global.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@AllArgsConstructor
@JsonPropertyOrder({"timestamp", "code", "message", "result"})
public class BaseResponse<T> {

    private final LocalDateTime timestamp = LocalDateTime.now();

    private final String code;

    private final String message;

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private T result;

    public static <T> BaseResponse<T> onSuccess(T result) {
        return new BaseResponse<>("COMMON200", "요청에 성공하였습니다.", result);
    }

    public static BaseResponse<Void> onSuccess() {
        return new BaseResponse<>("COMMON200", "요청에 성공하였습니다.", null);
    }

    public static <T> BaseResponse<T> onFailure(String code, String message, T data) {
        return new BaseResponse<>(code, message, data);
    }
}
