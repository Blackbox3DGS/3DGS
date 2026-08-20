package com.youthfi.auth.domain.job;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class JobRequest {

    // 업로드된 파일 이름 또는 경로
    private String fileName;

    // 필요하면 추가 가능 (옵션)
    // private String description;
}