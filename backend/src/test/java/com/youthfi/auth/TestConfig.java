package com.youthfi.auth;

import com.youthfi.auth.domain.job.JobWorker;
import org.mockito.Mockito;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

@TestConfiguration
public class TestConfig {
    
    @Bean
    @Primary // 💡 실제 JobWorker 대신 이 Mock 객체가 모든 곳에 우선 주입됩니다.
    public JobWorker jobWorker() {
        return Mockito.mock(JobWorker.class);
    }
}