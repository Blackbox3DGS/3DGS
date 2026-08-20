package com.youthfi.auth;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean; // 스프링 3.4+ 방식
import com.youthfi.auth.domain.job.JobWorker;

@SpringBootTest
class AuthApplicationTests {

    @MockitoBean // 💡 실제 Redis를 쓰는 JobWorker 대신 가짜를 주입해 컨텍스트 에러를 막음
    private JobWorker jobWorker;

    @Test
    void contextLoads() {
    }
}