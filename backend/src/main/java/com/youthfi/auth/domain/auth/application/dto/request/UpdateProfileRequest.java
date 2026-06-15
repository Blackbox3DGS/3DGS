package com.youthfi.auth.domain.auth.application.dto.request;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;

public record UpdateProfileRequest(
        @NotBlank String name,
        @NotBlank String birth,
        String currentPassword,
        String newPassword
) {
    @AssertTrue(message = "currentPassword is required when newPassword is provided")
    public boolean isPasswordChangeValid() {
        if (newPassword == null || newPassword.isBlank()) return true; // 변경 안 함
        return currentPassword != null && !currentPassword.isBlank();  // 변경 시 현재 비번 필수
    }
}