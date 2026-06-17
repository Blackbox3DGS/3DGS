package com.youthfi.auth.domain.job;

import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ReconstructionJobRepository extends JpaRepository<JobEntity, String> {
    // 특정 유저의 영상 중 제목 검색 + 정렬
    List<JobEntity> findByUserUserIdAndCustomTitleContaining(String userId, String title, Sort sort);

    // 특정 유저의 영상 중 상태 필터(완료/처리중) + 정렬
    List<JobEntity> findByUserUserIdAndStatus(String userId, JobStatus status, Sort sort);

    // 특정 유저의 전체 목록 + 정렬
    List<JobEntity> findByUserUserId(String userId, Sort sort);
}