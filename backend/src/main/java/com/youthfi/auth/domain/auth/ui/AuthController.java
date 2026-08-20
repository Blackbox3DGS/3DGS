package com.youthfi.auth.domain.auth.ui;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.youthfi.auth.domain.auth.application.dto.request.LoginRequest;
import com.youthfi.auth.domain.auth.application.dto.request.SignUpRequest;
import com.youthfi.auth.domain.auth.application.dto.request.TokenReissueRequest;
import com.youthfi.auth.domain.auth.application.dto.response.LoginResponse;
import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.domain.auth.application.usecase.UserAuthUseCase;
import com.youthfi.auth.global.annotation.CurrentUser;
import com.youthfi.auth.global.common.BaseResponse;
import com.youthfi.auth.global.swagger.AuthApi;

import io.swagger.v3.oas.annotations.Parameter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/auth")
public class AuthController implements AuthApi {

    private final UserAuthUseCase userAuthUseCase;

    @PostMapping("/signup")
    @Override
    public BaseResponse<Void> signup(@Valid @RequestBody SignUpRequest request) {
        userAuthUseCase.signUp(request);
        return BaseResponse.onSuccess();
    }

    @PostMapping("/login")
    @Override
    public BaseResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return BaseResponse.onSuccess(userAuthUseCase.login(request));
    }

    @DeleteMapping("/logout")
    @Override
    public BaseResponse<Void> logout(HttpServletRequest request) {
        userAuthUseCase.logout(request);
        return BaseResponse.onSuccess();
    }

    @DeleteMapping("/logout/user")
    public BaseResponse<Void> logoutByUserId(@Parameter(hidden = true) @CurrentUser String userId) {
        userAuthUseCase.logout(userId);
        return BaseResponse.onSuccess();
    }

    @PostMapping("/reissue")
    @Override
    public BaseResponse<TokenReissueResponse> reissueToken(@Valid @RequestBody TokenReissueRequest request) {
        return BaseResponse.onSuccess(userAuthUseCase.reissueToken(request));
    }

    @PostMapping("/verify")
    public BaseResponse<Void> verifyToken(HttpServletRequest request, HttpServletResponse response) {
        String userId = userAuthUseCase.verifyToken(request);
        response.setHeader("X-User-Id", userId);
        return BaseResponse.onSuccess();
    }
    
    // 👈 소셜 로그인 관련 수동 PostMapping 메서드를 통째로 삭제했습니다!
}