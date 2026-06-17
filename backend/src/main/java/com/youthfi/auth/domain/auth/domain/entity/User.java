package com.youthfi.auth.domain.auth.domain.entity;

import com.youthfi.auth.global.common.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@Table(
    name = "users",
    uniqueConstraints = {
        @UniqueConstraint(name = "uk_provider_provider_user_id", columnNames = {"social_provider", "provider_user_id"})
    }
)
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class User extends BaseEntity {

    @Id
    @Column(nullable = false, unique = true)
    private String userId;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false, unique = true)
    private String email;

    // 1. 소셜 사용자를 위해 비밀번호와 생일은 nullable = true로 설정
    @Column(nullable = true)
    private String password;

    @Column(nullable = true)
    private String birth;

    // 2. 누락되었던 소셜 로그인 관련 필드 복구
    @Enumerated(EnumType.STRING)
    @Column(name = "social_provider")
    private SocialProvider socialProvider;

    @Column(name = "provider_user_id")
    private String providerUserId;

    @Column
    private Boolean emailVerified;

    @Column
    private String profileImageUrl;

    // 3. 누락되었던 소셜 연동 메서드 복구 (SocialOAuthService 에러 해결)
    public void linkSocial(SocialProvider provider, String providerUserId, Boolean emailVerified, String profileImageUrl) {
        this.socialProvider = provider;
        this.providerUserId = providerUserId;
        this.emailVerified = emailVerified;
        this.profileImageUrl = profileImageUrl;
    }

    // 4. 누락되었던 프로필 업데이트 메서드 복구 (UpdateProfileUseCase 에러 해결)
    public void updateProfile(String name, String birth, String encodedNewPassword) {
        this.name = name;
        this.birth = birth;
        if (encodedNewPassword != null && !encodedNewPassword.isBlank()) {
            this.password = encodedNewPassword;
        }
    }
}