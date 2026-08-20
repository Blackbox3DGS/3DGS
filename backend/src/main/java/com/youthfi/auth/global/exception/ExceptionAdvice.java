package com.youthfi.auth.global.exception;

import com.youthfi.auth.global.common.BaseResponse;
import com.youthfi.auth.global.exception.code.BaseCode;
import com.youthfi.auth.global.exception.code.status.GlobalErrorStatus;
import jakarta.validation.ConstraintViolationException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.lang.NonNull; // 추가됨
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@Slf4j
@RestControllerAdvice(annotations = {RestController.class})
@RequiredArgsConstructor
public class ExceptionAdvice extends ResponseEntityExceptionHandler {

    @ExceptionHandler(Exception.class)
    public ResponseEntity<BaseResponse<String>> handle500Exception(Exception e) {
        log.error("[handle500] unexpected exception: {}", e.getMessage(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(BaseResponse.onFailure(GlobalErrorStatus._INTERNAL_SERVER_ERROR.getCode().getCode(),
                        "서버 내부 오류가 발생했습니다.", null));
    }

    /*
     * 직접 정의한 RestApiException 에러 클래스에 대한 예외 처리
     */
    @ExceptionHandler(value = RestApiException.class)
    public ResponseEntity<BaseResponse<String>> handleRestApiException(RestApiException e) {
        log.warn("[handleRestApiException] code={} message={}",
                e.getErrorCode().getCode(), e.getErrorCode().getMessage());
        BaseCode errorCode = e.getErrorCode();
        return handleExceptionInternal(errorCode);
    }

    /*
     * DataIntegrityViolationException 발생 시 예외 처리
     */
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<BaseResponse<String>> handleDataIntegrityViolation(DataIntegrityViolationException e) {
        log.warn("[handleDataIntegrityViolation] database constraint violation: {}", e.getMessage());
        String message = "데이터 저장 중 제약조건 위반이 발생했습니다. 필수 필드를 확인해주세요.";
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(BaseResponse.onFailure(GlobalErrorStatus._VALIDATION_ERROR.getCode().getCode(), message, null));
    }

    /*
     * ConstraintViolationException 발생 시 예외 처리
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<BaseResponse<String>> handleConstraintViolationException(ConstraintViolationException e) {
        log.warn("[handleConstraintViolation] validation failed: {}", e.getMessage());
        return handleExceptionInternal(GlobalErrorStatus._VALIDATION_ERROR.getCode());
    }

    /*
     * MethodArgumentTypeMismatchException 발생 시 예외 처리
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<BaseResponse<String>> handleMethodArgumentTypeMismatch(MethodArgumentTypeMismatchException e) {
        log.warn("[handleTypeMismatch] param={} invalid type: {}", e.getName(), e.getValue());
        return handleExceptionInternal(GlobalErrorStatus._METHOD_ARGUMENT_ERROR.getCode());
    }

    /*
     * MethodArgumentNotValidException 발생 시 예외 처리
     * 부모 클래스의 규칙에 따라 @NonNull 어노테이션을 파라미터에 추가함
     */
    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
            @NonNull MethodArgumentNotValidException e, 
            @NonNull HttpHeaders headers, 
            @NonNull HttpStatusCode statusCode, 
            @NonNull WebRequest request) {
        
        log.warn("[handleNotValid] binding errors={}", e.getBindingResult().getFieldErrors());
        Map<String, String> errors = new LinkedHashMap<>();

        e.getBindingResult().getFieldErrors().forEach(fieldError -> {
            String fieldName = fieldError.getField();
            String errorMessage = Optional.ofNullable(fieldError.getDefaultMessage()).orElse("");
            errors.merge(fieldName, errorMessage, (existingErrorMessage, newErrorMessage) -> existingErrorMessage + ", " + newErrorMessage);
        });

        return handleExceptionInternalArgs(GlobalErrorStatus._VALIDATION_ERROR.getCode(), errors);
    }

    private ResponseEntity<BaseResponse<String>> handleExceptionInternal(BaseCode errorCode) {
        return ResponseEntity
                .status(errorCode.getHttpStatus().value())
                .body(BaseResponse.onFailure(errorCode.getCode(), errorCode.getMessage(), null));
    }

    private ResponseEntity<Object> handleExceptionInternalArgs(BaseCode errorCode, Map<String, String> errorArgs) {
        return ResponseEntity
                .status(errorCode.getHttpStatus().value())
                .body(BaseResponse.onFailure(errorCode.getCode(), errorCode.getMessage(), errorArgs));
    }

    // 💡 사용하지 않던 handleExceptionInternalFalse 메서드는 삭제되었습니다.
}