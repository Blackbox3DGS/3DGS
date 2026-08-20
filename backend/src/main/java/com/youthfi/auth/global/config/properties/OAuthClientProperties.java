package com.youthfi.auth.global.config.properties;

import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@ConfigurationProperties(prefix = "auth.oauth2")
public class OAuthClientProperties {
    private Map<String, Client> clients;

    @Getter
    @Setter
    public static class Client {
        private String clientId;
        private String clientSecret;
        private String redirectUri;
    }
}


