package com.youthfi.auth.domain.auth.domain.service;

import com.youthfi.auth.domain.auth.application.dto.request.SignUpRequest;
import com.youthfi.auth.domain.auth.application.dto.response.ProfileResponse;
import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.domain.auth.domain.repository.UserRepository;
import com.youthfi.auth.global.exception.RestApiException;
import com.youthfi.auth.global.exception.code.status.AuthErrorStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
@SuppressWarnings("null") // 💡 이 줄이 핵심입니다! Null 관련 잔소리를 멈추게 합니다.
public class UserService {

    private final UserRepository userRepository;

    // 1️⃣ 유저 찾기 (알맹이 반환)
    public User findUser(String userId) {
        return userRepository.findByUserId(userId)
                .orElseThrow(() -> new RestApiException(AuthErrorStatus.INVALID_ACCESS_TOKEN));
    }

    // 2️⃣ 유저 찾기 (상자/Optional 반환 - 테스트 코드용)
    public Optional<User> findByUserId(String userId) {
        return userRepository.findByUserId(userId);
    }

    // 3️⃣ 이메일 중복 체크
    public boolean isAlreadyRegistered(String email) {
        return userRepository.existsByEmail(email);
    }

    // 4️⃣ 아이디 중복 체크
    public boolean isUserIdAlreadyRegistered(String userId) {
        return userRepository.existsByUserId(userId);
    }

    // 5️⃣ 일반 회원가입 저장
    public User save(SignUpRequest request) {
        User user = User.builder()
                .userId(request.userId())
                .email(request.email())
                .password(request.password())
                .name(request.name())
                .birth(request.birth())
                .build();
        return userRepository.save(user); // 💡 여기서 나던 경고가 사라집니다.
    }

    // 6️⃣ 소셜 로그인 유저 처리 (Naver 전용)
    public void registerOrUpdateSocialUser(String userId, String email, String name) {
        Optional<User> userOptional = userRepository.findByUserId(userId);

        if (userOptional.isPresent()) {
            log.info("기존 소셜 유저 로그인: {}", userId);
        } else {
            User newUser = User.builder()
                    .userId(userId)
                    .email(email)
                    .name(name)
                    .password("SOCIAL_AUTH")
                    .build();
            
            userRepository.save(newUser);
            log.info("새로운 소셜 유저 가입: {}", userId);
        }
    }

    // 7️⃣ 프로필 정보 조회
    public ProfileResponse findProfile(String userId) {
        User user = findUser(userId); // 💡 여기서 나던 경고도 사라집니다.
        return new ProfileResponse(
                user.getUserId(),
                user.getEmail(),
                user.getName(),
                user.getBirth()
        );
    }
}