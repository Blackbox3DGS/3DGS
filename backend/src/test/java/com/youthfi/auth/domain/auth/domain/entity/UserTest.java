package com.youthfi.auth.domain.auth.domain.entity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

@DisplayName("User 엔티티 테스트")
class UserTest {

    private User user;

    @BeforeEach
    void setUp() {
        user = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();
    }

    @Test
    @DisplayName("User 엔티티 생성 성공")
    void createUser_Success() {
        // given & when
        User newUser = User.builder()
                .userId("newuser")
                .email("new@example.com")
                .password("newPassword")
                .name("김철수")
                .birth("1985-05-15")
                .build();

        // then
        assertNotNull(newUser);
        assertEquals("newuser", newUser.getUserId());
        assertEquals("new@example.com", newUser.getEmail());
        assertEquals("newPassword", newUser.getPassword());
        assertEquals("김철수", newUser.getName());
        assertEquals("1985-05-15", newUser.getBirth());
    }

    @Test
    @DisplayName("User 엔티티 생성 - 모든 필드 null")
    void createUser_WithAllNullFields() {
        // given & when
        User newUser = User.builder()
                .userId(null)
                .email(null)
                .password(null)
                .name(null)
                .birth(null)
                .build();

        // then
        assertNotNull(newUser);
        assertNull(newUser.getUserId());
        assertNull(newUser.getEmail());
        assertNull(newUser.getPassword());
        assertNull(newUser.getName());
        assertNull(newUser.getBirth());
    }

    @Test
    @DisplayName("User 엔티티 생성 - 빈 문자열 필드")
    void createUser_WithEmptyStringFields() {
        // given & when
        User newUser = User.builder()
                .userId("")
                .email("")
                .password("")
                .name("")
                .birth("")
                .build();

        // then
        assertNotNull(newUser);
        assertEquals("", newUser.getUserId());
        assertEquals("", newUser.getEmail());
        assertEquals("", newUser.getPassword());
        assertEquals("", newUser.getName());
        assertEquals("", newUser.getBirth());
    }

    @Test
    @DisplayName("프로필 업데이트 - 모든 필드 업데이트")
    void updateProfile_AllFields() {
        // given
        String newName = "김철수";
        String newBirth = "1985-05-15";
        String newPassword = "newEncodedPassword";

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        assertEquals(newPassword, user.getPassword());
        // 다른 필드는 변경되지 않음
        assertEquals("testuser", user.getUserId());
        assertEquals("test@example.com", user.getEmail());
    }

    @Test
    @DisplayName("프로필 업데이트 - 이름과 생년월일만 업데이트")
    void updateProfile_NameAndBirthOnly() {
        // given
        String newName = "김철수";
        String newBirth = "1985-05-15";
        String newPassword = null;

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        // 비밀번호는 변경되지 않음 (null이므로)
        assertEquals("encodedPassword", user.getPassword());
        // 다른 필드는 변경되지 않음
        assertEquals("testuser", user.getUserId());
        assertEquals("test@example.com", user.getEmail());
    }

    @Test
    @DisplayName("프로필 업데이트 - 빈 문자열 비밀번호")
    void updateProfile_EmptyStringPassword() {
        // given
        String newName = "김철수";
        String newBirth = "1985-05-15";
        String newPassword = "";

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        // 빈 문자열이므로 비밀번호는 변경되지 않음
        assertEquals("encodedPassword", user.getPassword());
    }

    @Test
    @DisplayName("프로필 업데이트 - 공백만 있는 비밀번호")
    void updateProfile_BlankPassword() {
        // given
        String newName = "김철수";
        String newBirth = "1985-05-15";
        String newPassword = "   ";

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        // 공백만 있으므로 비밀번호는 변경되지 않음
        assertEquals("encodedPassword", user.getPassword());
    }

    @Test
    @DisplayName("프로필 업데이트 - 유효한 비밀번호")
    void updateProfile_ValidPassword() {
        // given
        String newName = "김철수";
        String newBirth = "1985-05-15";
        String newPassword = "newValidPassword";

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        assertEquals(newPassword, user.getPassword());
    }

    @Test
    @DisplayName("프로필 업데이트 - null 값들")
    void updateProfile_NullValues() {
        // given
        String newName = null;
        String newBirth = null;
        String newPassword = null;

        // when
        user.updateProfile(newName, newBirth, newPassword);

        // then
        assertEquals(newName, user.getName());
        assertEquals(newBirth, user.getBirth());
        // 비밀번호는 null이므로 변경되지 않음
        assertEquals("encodedPassword", user.getPassword());
    }

    @Test
    @DisplayName("User 엔티티 equals 테스트")
    void testUserEquals() {
        // given
        User user1 = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        User user2 = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        User user3 = User.builder()
                .userId("differentuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        // when & then
        // User 엔티티는 equals/hashCode가 구현되지 않았으므로 참조 비교
        assertNotEquals(user1, user2); // 다른 인스턴스이므로 false
        assertNotEquals(user1, user3);
        assertNotEquals(user2, user3);
    }

    @Test
    @DisplayName("User 엔티티 hashCode 테스트")
    void testUserHashCode() {
        // given
        User user1 = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        User user2 = User.builder()
                .userId("testuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        User user3 = User.builder()
                .userId("differentuser")
                .email("test@example.com")
                .password("encodedPassword")
                .name("홍길동")
                .birth("1990-01-01")
                .build();

        // when & then
        // User 엔티티는 equals/hashCode가 구현되지 않았으므로 다른 해시코드
        assertNotEquals(user1.hashCode(), user2.hashCode());
        assertNotEquals(user1.hashCode(), user3.hashCode());
    }

    @Test
    @DisplayName("User 엔티티 toString 테스트")
    void testUserToString() {
        // when
        String toString = user.toString();

        // then
        assertNotNull(toString);
        assertTrue(toString.contains("User"));
        // toString은 기본 Object.toString()을 사용하므로 클래스명과 해시코드만 포함
        // 필드 값들은 포함되지 않을 수 있음
    }

    @Test
    @DisplayName("User 엔티티 getter 메서드 테스트")
    void testUserGetters() {
        // when & then
        assertEquals("testuser", user.getUserId());
        assertEquals("test@example.com", user.getEmail());
        assertEquals("encodedPassword", user.getPassword());
        assertEquals("홍길동", user.getName());
        assertEquals("1990-01-01", user.getBirth());
    }

    @Test
    @DisplayName("User 엔티티 빌더 패턴 테스트")
    void testUserBuilderPattern() {
        // given
        User.UserBuilder builder = User.builder();

        // when
        User newUser = builder
                .userId("builderuser")
                .email("builder@example.com")
                .password("builderPassword")
                .name("빌더사용자")
                .birth("1995-12-25")
                .build();

        // then
        assertNotNull(newUser);
        assertEquals("builderuser", newUser.getUserId());
        assertEquals("builder@example.com", newUser.getEmail());
        assertEquals("builderPassword", newUser.getPassword());
        assertEquals("빌더사용자", newUser.getName());
        assertEquals("1995-12-25", newUser.getBirth());
    }

    @Test
    @DisplayName("User 엔티티 - 다양한 이름 형식 테스트")
    void testUserWithVariousNameFormats() {
        String[] names = {
                "홍길동",
                "김철수",
                "이영희",
                "John Doe",
                "김",
                "Very Long Name With Many Characters",
                "이름123",
                "Name-With-Dashes",
                "Name_With_Underscores"
        };

        for (String name : names) {
            // given & when
            User newUser = User.builder()
                    .userId("testuser")
                    .email("test@example.com")
                    .password("password")
                    .name(name)
                    .birth("1990-01-01")
                    .build();

            // then
            assertEquals(name, newUser.getName());
        }
    }

    @Test
    @DisplayName("User 엔티티 - 다양한 생년월일 형식 테스트")
    void testUserWithVariousBirthFormats() {
        String[] births = {
                "1990-01-01",
                "1985-12-31",
                "2000-06-15",
                "1970-03-30",
                "2020-01-01",
                "1950-11-11"
        };

        for (String birth : births) {
            // given & when
            User newUser = User.builder()
                    .userId("testuser")
                    .email("test@example.com")
                    .password("password")
                    .name("홍길동")
                    .birth(birth)
                    .build();

            // then
            assertEquals(birth, newUser.getBirth());
        }
    }
}
