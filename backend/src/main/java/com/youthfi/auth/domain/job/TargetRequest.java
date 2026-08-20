package com.youthfi.auth.domain.job;

import lombok.Data;
import java.util.List;

@Data
public class TargetRequest {
    private List<Integer> targetIds;
}