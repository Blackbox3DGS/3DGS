package com.youthfi.auth.global.swagger;

import com.youthfi.auth.domain.auth.application.dto.request.LoginRequest;
import com.youthfi.auth.domain.auth.application.dto.request.SignUpRequest;
import com.youthfi.auth.domain.auth.application.dto.request.TokenReissueRequest;
import com.youthfi.auth.domain.auth.application.dto.response.LoginResponse;
import com.youthfi.auth.domain.auth.application.dto.response.TokenReissueResponse;
import com.youthfi.auth.global.common.BaseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;

/**
 * 인증 관련 API 인터페이스
 */
@Tag(name = "인증 관리", description = "사용자 인증, 회원가입, 로그인, 로그아웃")
public interface AuthApi extends BaseApi {

    @Operation(
            summary = "회원가입",
            description = "새로운 사용자를 등록합니다. userId는 고유해야 하며, 이메일도 중복되지 않아야 합니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "201",
                    description = "회원가입 성공",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "400",
                    description = "잘못된 요청 (중복된 userId 또는 이메일)",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<?> signup(SignUpRequest request);

    @Operation(
            summary = "로그인",
            description = "userId와 password를 사용하여 로그인합니다. 성공 시 access token과 refresh token을 반환합니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "로그인 성공",
                    content = @Content(schema = @Schema(implementation = LoginResponse.class))
            ),
            @ApiResponse(
                    responseCode = "401",
                    description = "로그인 실패 (잘못된 userId 또는 password)",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<LoginResponse> login(LoginRequest request);

    @Operation(
            summary = "로그아웃",
            description = "현재 사용자를 로그아웃하고 access token을 블랙리스트에 추가합니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "로그아웃 성공",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "401",
                    description = "인증 실패",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<?> logout(HttpServletRequest request);

    @Operation(
            summary = "토큰 재발급",
            description = "refresh token을 사용하여 새로운 access token을 발급받습니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "토큰 재발급 성공",
                    content = @Content(schema = @Schema(implementation = TokenReissueResponse.class))
            ),
            @ApiResponse(
                    responseCode = "400",
                    description = "잘못된 refresh token",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "401",
                    description = "만료된 refresh token",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<TokenReissueResponse> reissueToken(TokenReissueRequest request);
    
}