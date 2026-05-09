package com.youthfi.auth.domain.job;

import com.youthfi.auth.domain.auth.domain.entity.User;
import com.youthfi.auth.global.annotation.CurrentUser;
import com.youthfi.auth.global.common.BaseResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.io.File;
import java.util.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/reconstruction")
public class JobController {
    private final JobService jobService;

    @PostMapping("/upload")
    public BaseResponse<String> createJob(@CurrentUser User user, @RequestParam("file") MultipartFile file) {
        String path = "/Users/kim-wonjun/uploads/" + UUID.randomUUID() + "_" + file.getOriginalFilename();
        try {
            file.transferTo(new File(path));
            return BaseResponse.onSuccess(jobService.createJob(user, path));
        } catch (Exception e) { return BaseResponse.onFailure("500", "업로드 실패", null); }
    }

    @GetMapping
    public BaseResponse<List<JobStatusResponse>> getMyJobs(
            @CurrentUser User user,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) JobStatus status,
            @RequestParam(defaultValue = "createdAt") String sortBy) {
        
        List<JobEntity> jobs = jobService.searchJobs(user, keyword, status, sortBy);
        return BaseResponse.onSuccess(jobs.stream().map(JobStatusResponse::from).toList());
    }

    @GetMapping("/{jobId}")
    public BaseResponse<JobStatusResponse> getStatus(@PathVariable String jobId) {
        return BaseResponse.onSuccess(jobService.getJob(jobId));
    }

    @PatchMapping("/{jobId}/title")
    public BaseResponse<String> renameJob(@CurrentUser User user, @PathVariable String jobId, @RequestParam String newTitle) {
        jobService.updateCustomTitle(jobId, newTitle, user);
        return BaseResponse.onSuccess("제목 변경 완료");
    }

    @PostMapping("/{jobId}/target")
    public BaseResponse<String> setTarget(@CurrentUser User user, @PathVariable String jobId, @RequestBody TargetRequest request) {
        jobService.saveTargetIds(jobId, request.getTargetIds(), user);
        return BaseResponse.onSuccess("타겟 설정 완료");
    }

    // [추가] 분석 기록 삭제 (본인 소유만 가능)
    @DeleteMapping("/{jobId}")
    public BaseResponse<String> deleteJob(@CurrentUser User user, @PathVariable String jobId) {
        jobService.deleteJob(jobId, user);
        return BaseResponse.onSuccess("삭제 완료");
    }
}
