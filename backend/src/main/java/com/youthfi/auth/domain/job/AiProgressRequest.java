package com.youthfi.auth.domain.job;

import lombok.Data;

@Data
public class AiProgressRequest {
    private int progress;
    private String step;
    private String status;
}