# 3DGS 메인 백엔드 서버 (Spring Boot)

## 1. 개요
본 프로젝트는 단안 영상 기반 3DGS(3D Gaussian Splatting) 재구성 시스템의 메인 백엔드 서버입니다. 프론트엔드와 AI 파이프라인(FastAPI) 사이에서 API 게이트웨이 및 비동기 작업 스케줄링 역할을 수행하며, 시스템의 안정성과 대용량 파일 처리 효율성을 고려하여 설계되었습니다.

## 2. 아키텍처 구조
* **인증(Auth) 서비스 연동**: 외부 모듈인 `BE-auth-service`를 통해 회원의 JWT 토큰을 넘겨받아 유효성을 검증하고 요청자의 식별자(UserId)를 획득합니다.
* **스토리지 계층 (GCS Direct Upload)**: 백엔드 서버의 네트워크 병목(OOM 및 대역폭 고갈)을 방지하기 위해 클라이언트에 GCS Signed URL을 발급합니다. 실제 영상 업로드는 클라이언트와 GCS 간 직접 통신으로 이루어집니다.
* **메시지 큐 기반 비동기 처리**: AI 서버(FastAPI)로의 직접적인 HTTP 요청이 발생시킬 수 있는 리소스 경합 및 장애 전파를 차단하기 위해 Message Queue (Redis Stream 또는 RabbitMQ)를 도입합니다.
* **Webhook 및 멱등성 보장**: AI 파이프라인의 처리 결과(완료/실패)는 Webhook을 통해 수신하며, 네트워크 재시도 상황을 고려해 동일한 Task ID에 대한 처리 로직은 멱등성(Idempotency)을 보장합니다.

## 3. 기술 스택
* **Language & Framework**: Java 17, Spring Boot 3.x
* **Database**: MySQL 8.0 (또는 PostgreSQL 15+), Spring Data JPA
* **Message Broker**: Redis Stream 또는 RabbitMQ
* **Cloud Storage**: Google Cloud Storage (GCS)
* **API Documentation**: Springdoc OpenAPI (Swagger)
* **Observability (추후 도입)**: Micrometer Tracing (분산 추적을 위한 TraceId 컨텍스트 전파)

## 4. 요구사항 정의서

| 요구사항 ID | 액터 | 도메인 | 기능명 | 상세 설명 | 우선순위 |
|---|---|---|---|---|---|
| REQ-ST-01 | 시스템 | 스토리지 | Signed URL 발급 | 클라이언트가 GCS 버킷에 파일을 직접 업로드할 수 있도록 10분 만료의 서명된 URL을 발급한다. | 1 |
| REQ-ST-02 | 시스템 | 스토리지 | 읽기 권한 분리 | 생성된 3D 모델(`.splat`) 데이터의 무단 핫링킹을 방지하기 위해, 조회 시점에만 5분 만료의 다운로드용 Signed URL을 생성하여 반환한다. | 1 |
| REQ-TK-01 | 시스템 | 작업 관리 | Task 생성 | 클라이언트가 업로드 완료 콜백을 호출하면, DB에 작업(`PENDING`) 메타데이터를 저장하고 Message Queue에 메시지를 발행(Publish)한다. | 1 |
| REQ-TK-02 | 파이프라인 | 작업 관리 | 상태 Webhook 수신 | AI 서버에서 특정 작업의 상태(`PROCESSING`, `COMPLETED`, `FAILED`)를 전달하는 콜백 API를 제공한다. 수신 시 멱등성을 보장해야 한다. | 1 |
| REQ-TK-03 | 시스템 | 작업 관리 | 동시성 및 할당량 제어 | 클라우드 인프라 자원 보호를 위해 사용자 1인당 동시 진행 가능한 활성 Task는 1개로 제한하며, 일일 변환 한도를 N회로 통제한다. | 1 |
| REQ-TK-04 | 시스템 | 장애 복구 | 좀비 Task 스케줄러 | `PROCESSING` 상태로 일정 시간(예: 3시간)을 초과한 Task는 AI 서버 장애로 간주하여 `FAILED` 상태로 일괄 변경(보상 트랜잭션)한다. | 2 |
| REQ-US-01 | 회원 | 조회 | 내 작업 목록 조회 | 사용자는 본인이 요청한 작업 내역을 최신순으로 페이징하여 조회할 수 있다. | 2 |
| REQ-US-02 | 회원 | 조회 | 상세 조회 및 삭제 | 사용자는 단일 작업의 진행 상태 및 만료형 뷰어 URL을 조회할 수 있으며, 본인의 Task를 물리 삭제할 수 있다. (삭제 시 GCS 파일 동기 삭제) | 1 |
| REQ-SEC-01| 시스템 | API 보안 | JWT 유효성 검증 | 인증이 필요한 모든 API는 헤더의 `Bearer Token`에 대해 서명(Signature)과 만료 일시를 검증한다. | 1 |

## 5. 작업 상태 전이 (State Machine)
작업(Task) 엔티티는 아래의 생명주기를 가지며, 허용되지 않은 상태 전이 시 예외를 발생시킵니다.
1. `READY`: 클라이언트가 Signed URL을 발급받은 직후의 가 상태 (옵션).
2. `PENDING`: 클라이언트가 파일 업로드를 마치고 작업을 최종 큐에 인입시킨 상태.
3. `PROCESSING`: AI 파이프라인이 큐에서 작업을 꺼내어 GPU 연산을 진행 중인 상태.
4. `COMPLETED`: 변환이 정상 종료되고 결과물(`.splat`) GCS URL 정보가 반영된 최종 상태.
5. `FAILED`: 분석 중 오류가 발생했거나, 시스템 타임아웃에 의해 강제로 작업이 종료된 상태.

## 6. 핵심 API 명세

### 6.1 GCS 임시 업로드 서명 발급
* **Endpoint**: `POST /api/v1/tasks/upload-url`
* **Request**: `{"filename": "video.mp4", "contentType": "video/mp4"}`
* **Response (200)**: `{"uploadUrl": "https://storage...", "gcsPathKey": "videos/...", "expiresIn": 600}`

### 6.2 변환 작업 등록 및 큐 인입
* **Endpoint**: `POST /api/v1/tasks`
* **Request**: `{"gcsPathKey": "videos/...", "title": "사고 영상"}`
* **Response (201)**: `{"taskId": "UUID-...", "status": "PENDING"}`
* **Error**: `429 Too Many Requests` (일일 한도 초과), `409 Conflict` (이미 진행 중인 작업 존재)

### 6.3 작업 상태 및 결과물 조회
* **Endpoint**: `GET /api/v1/tasks/{taskId}`
* **Response (200)**: 
  ```json
  {
    "taskId": "UUID-...",
    "status": "COMPLETED",
    "viewerUrl": "https://storage...(만료 적용)",
    "videoUrl": "https://storage...(만료 적용)"
  }
  ```

### 6.4 AI 파이프라인 콜백 (내부망 전용)
* **Endpoint**: `POST /api/v1/internal/webhook/task-status`
* **Header**: `x-internal-secret: <VPC_SECRET_KEY>`
* **Request**: `{"taskId": "UUID-...", "status": "COMPLETED", "resultGcsKey": "splats/..."}`
* **Response (200)**: 성공 응답. 멱등성 보장 (이미 `COMPLETED`인 경우 무시 후 200 응답).

## 7. 디렉터리 구조 (Domain Driven Design 적용)
```text
/src/main/java/com/dgs/main/
├── global                  
│   ├── config              # GCS, Redis MQ, CORS, Security 설정
│   ├── exception           # 전역 예외 처리 및 ErrorCode 관리 (4xx, 5xx 에러 포맷)
│   └── security            # JWT 파서 및 인증 컨텍스트
├── infra                   
│   ├── gcs                 # Signed URL 발급 및 Object 관리 인터페이스
│   └── messaging           # Message Queue Producer 구현체
└── domain                  
    ├── task                # 메인 비즈니스 도메인
    │   ├── controller      # API 엔드포인트
    │   ├── service         # 분산 락, 트랜잭션 관리, 상태 전이 로직
    │   ├── entity          # RDBMS 테이블 매핑
    │   └── dto             
    └── webhook             # 콜백 수신 및 데이터 병합 영역
```
