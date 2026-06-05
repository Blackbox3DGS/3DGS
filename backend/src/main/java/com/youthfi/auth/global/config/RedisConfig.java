package com.youthfi.auth.global.config;

import java.util.Objects;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;
import org.springframework.lang.NonNull; // 추가됨

@Configuration
// 💡 15번 줄의 @SuppressWarnings("null")을 제거했습니다.
public class RedisConfig {

    @Value("${spring.data.redis.host:localhost}")
    private String host;

    @Value("${spring.data.redis.port:6379}")
    private int port;

    @Bean
    @NonNull // 빈 생성 시 Null이 아님을 명시
    public RedisConnectionFactory redisConnectionFactory() {

        String safeHost = Objects.requireNonNull(host, "Redis host must not be null");

        return new LettuceConnectionFactory(safeHost, port);
    }

    @Bean
    @NonNull
    public RedisTemplate<String, Object> redisTemplate(
            @NonNull RedisConnectionFactory connectionFactory // 파라미터에 @NonNull 추가
    ) {

        RedisTemplate<String, Object> template = new RedisTemplate<>();

        template.setConnectionFactory(
                Objects.requireNonNull(connectionFactory, "connectionFactory must not be null")
        );

        StringRedisSerializer stringSerializer = new StringRedisSerializer();
        GenericJackson2JsonRedisSerializer jsonSerializer =
                new GenericJackson2JsonRedisSerializer();

        // key
        template.setKeySerializer(stringSerializer);

        // value
        template.setValueSerializer(jsonSerializer);

        // hash
        template.setHashKeySerializer(stringSerializer);
        template.setHashValueSerializer(jsonSerializer);

        template.afterPropertiesSet();

        return template;
    }
}