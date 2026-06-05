package com.youthfi.auth.global.swagger;

import com.youthfi.auth.domain.auth.application.dto.request.UpdateProfileRequest;
import com.youthfi.auth.domain.auth.application.dto.response.ProfileResponse;
import com.youthfi.auth.global.common.BaseResponse;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;

/**
 * 사용자 프로필 관리 API 인터페이스 (UserController용)
 */
@Tag(name = "사용자 프로필", description = "사용자 프로필 조회 및 수정 API")
public interface UserProfileApi extends BaseApi {

    @Operation(
            summary = "프로필 조회",
            description = "현재 로그인한 사용자의 상세 프로필 정보를 조회합니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "프로필 조회 성공",
                    content = @Content(schema = @Schema(implementation = ProfileResponse.class))
            ),
            @ApiResponse(
                    responseCode = "401",
                    description = "인증 실패",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "404",
                    description = "사용자를 찾을 수 없음",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<ProfileResponse> getProfile(String userId);

    @Operation(
            summary = "프로필 수정",
            description = "사용자의 프로필 정보를 수정합니다. 비밀번호 변경 시 현재 비밀번호 확인이 필요합니다."
    )
    @ApiResponses(value = {
            @ApiResponse(
                    responseCode = "200",
                    description = "프로필 수정 성공",
                    content = @Content(schema = @Schema(implementation = ProfileResponse.class))
            ),
            @ApiResponse(
                    responseCode = "400",
                    description = "잘못된 요청 (유효성 검증 실패)",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "401",
                    description = "인증 실패 또는 현재 비밀번호 불일치",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            ),
            @ApiResponse(
                    responseCode = "404",
                    description = "사용자를 찾을 수 없음",
                    content = @Content(schema = @Schema(implementation = BaseResponse.class))
            )
    })
    BaseResponse<ProfileResponse> updateProfile(String userId, UpdateProfileRequest request);
}
