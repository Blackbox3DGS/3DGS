package com.youthfi.auth.global.security;

import lombok.AllArgsConstructor;
import lombok.Getter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

@Getter
@AllArgsConstructor
@ConfigurationProperties("exclude-blacklist-path-patterns")
public class ExcludeBlacklistPathProperties {
    private List<AuthPath> paths;

    public List<String> getExcludeAuthPaths() {
        return paths.stream().map(AuthPath::getPathPattern).toList();
    }

    @Getter
    @AllArgsConstructor
    public static class AuthPath {
        private String pathPattern;
        private String method;
    }
}