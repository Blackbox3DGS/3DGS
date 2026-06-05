package com.youthfi.auth.domain.job;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ResumeRequest {
    private String jobId;
    private List<Integer> targetIds;
}