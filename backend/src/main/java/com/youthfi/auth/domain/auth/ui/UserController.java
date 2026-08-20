package com.youthfi.auth.domain.auth.ui;

import com.youthfi.auth.domain.auth.application.dto.request.UpdateProfileRequest;
import com.youthfi.auth.domain.auth.application.dto.response.ProfileResponse;
import com.youthfi.auth.domain.auth.application.usecase.UpdateProfileUseCase;
import com.youthfi.auth.domain.auth.application.usecase.UserProfileUseCase;
import com.youthfi.auth.global.annotation.CurrentUser;
import com.youthfi.auth.global.common.BaseResponse;
import com.youthfi.auth.global.swagger.UserProfileApi;
import io.swagger.v3.oas.annotations.Parameter;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/auth")
public class UserController implements UserProfileApi {

    private final UserProfileUseCase userProfileUseCase; // 조회
    private final UpdateProfileUseCase updateProfileUseCase; // 수정

    @GetMapping("/profile")
    @Override
    public BaseResponse<ProfileResponse> getProfile(
            @Parameter(hidden = true) @CurrentUser String userId) {
        ProfileResponse profile = userProfileUseCase.findProfile(userId);
        return BaseResponse.onSuccess(profile);
    }

    @PatchMapping("/profile")
    @Override
    public BaseResponse<ProfileResponse> updateProfile(
            @Parameter(hidden = true) @CurrentUser String userId,
            @Valid @RequestBody UpdateProfileRequest request) {
        ProfileResponse updated = updateProfileUseCase.update(userId, request);
        return BaseResponse.onSuccess(updated);
    }
}