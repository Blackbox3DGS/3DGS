FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN useradd -u 10001 -r -s /usr/sbin/nologin app

ARG JAR_FILE=build/libs/*.jar
COPY ${JAR_FILE} /app/app.jar

EXPOSE 8080
USER 10001
ENTRYPOINT ["java","-XX:MaxRAMPercentage=75","-jar","/app/app.jar"]