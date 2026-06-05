package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.global.common.BaseEntity;
import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Entity
@Getter @Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "jobs")
public class JobEntity extends BaseEntity {

    @Id
    private String jobId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false)
    private String originalFileName; 

    private String customTitle; 
    private String thumbnailUrl; // [추가] 리스트에 보여줄 영상 썸네일
    
    @Builder.Default
    private LocalDateTime incidentDate = LocalDateTime.now(); // [추가] 사고 발생 날짜

    @Enumerated(EnumType.STRING)
    private JobStatus status; 

    private int progress; // [와이어프레임 5번] 0~100% 진행률
    private String currentStep; // [와이어프레임 5번] "업로드 중...", "Step 2: 객체 탐지 중"

    private String targetIds; 
    private String resultUrl; // .splat (3D 뷰어용)
    private String trajectoryUrl; // .json (차량 궤적용)

    public void updateTitle(String newTitle) {
        if (newTitle != null && !newTitle.isBlank()) this.customTitle = newTitle;
    }

    public void assignTargets(List<Integer> targets) {
        if (targets != null && !targets.isEmpty()) {
            this.targetIds = targets.stream().map(String::valueOf).collect(Collectors.joining(","));
            this.status = JobStatus.PROCESSING;
        }
    }

    public void updateProgress(int progress, String currentStep, JobStatus status) {
        this.progress = progress;
        this.currentStep = currentStep;
        this.status = status;
    }

    @PrePersist
    public void init() {
        if (this.customTitle == null) this.customTitle = this.originalFileName;
        if (this.status == null) this.status = JobStatus.PENDING;
    }
}