package com.youthfi.auth.domain.auth.application.usecase;

import com.youthfi.auth.domain.auth.application.dto.response.ProfileResponse;
import com.youthfi.auth.domain.auth.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
@RequiredArgsConstructor
public class UserProfileUseCase {

    private final UserService userService;

    public ProfileResponse findProfile(String userId) {
        ProfileResponse profileDto = userService.findProfile(userId);

        return new ProfileResponse(
                profileDto.userId(),
                profileDto.email(),
                profileDto.name(),
                profileDto.birth()
        );
    }
}