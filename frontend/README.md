# 3D 사고 복원 시스템 - Frontend

블랙박스 영상을 업로드하면 AI 파이프라인이 사고 장면을 3D로 복원하고, 사용자가 차량 궤적과 충돌 정보를 웹에서 확인하는 시스템의 프론트엔드입니다.

---

## 기능

### 1. 인증
- Google / Kakao / Naver 소셜 로그인 (OAuth 2.0)
- 일반 아이디/비밀번호 로그인 및 회원가입
- JWT 액세스 토큰 + 리프레시 토큰 자동 재발급
- 데모 모드(백엔드 없이 더미 데이터로 UI 둘러보기)

### 2. 영상 업로드
- 드래그 앤 드롭 또는 파일 선택
- 최대 2GB, video/* 형식 검증
- 업로드 진행 중 상태 표시
- 업로드 직후 자동으로 분석 작업(Job) 시작

### 3. 분석 기록 목록
- 사용자가 업로드한 모든 영상의 분석 작업 표시
- 영상명(서버사이드 LIKE 검색, 300ms 디바운스)
- 사고 발생 날짜 범위 필터
- 업로드 날짜 범위 필터
- 5초 간격 자동 폴링(진행 중인 작업이 있을 때만)
- 작업 상태 뱃지: 대기 / 전처리 / 타겟 대기 / 처리 중 / 완료 / 실패
- 처리 중일 때 진행률 바 표시
- 전체보기 모달(테이블을 큰 화면에서 확인)

### 4. 영상명 변경
- 영상명 옆 연필 아이콘 클릭 → 인라인 편집
- Enter로 저장, Esc로 취소

### 5. 분석 기록 삭제
- 휴지통 아이콘 클릭 → 확인 다이얼로그
- 영상명을 다이얼로그에 표시해서 잘못 삭제 방지
- 삭제 성공/실패 토스트 알림

### 6. 3D 사고 복원 뷰어
- Gaussian Splat (.splat) 기반 3D 장면 렌더링
- 차량 A/B의 궤적 보간 재현
- 충돌 순간 차량 속도(km/h) 계산 및 표시
- 카메라 컨트롤: 마우스 좌클릭 드래그(회전), 휠(줌), 방향키(이동)
- 재생/일시정지, 배속(0.1~3.0x) 슬라이더
- 화면 맞추기(자동 카메라 위치 조정)
- 표시 옵션 토글: 차량 A, 차량 B, 궤적 라인, 사고 지점
- 자산이 없을 때 HTML 폴백 미리보기

---

## 폴더 구조

```text
frontend/
├── public/
│   ├── car-a.glb                          # 데모용 차량 A 모델
│   └── car-b.glb                          # 데모용 차량 B 모델
│
├── src/
│   ├── app/
│   │   ├── App.tsx                        # 라우터 정의, PrivateRoute / PublicRoute
│   │   │
│   │   ├── components/
│   │   │   ├── Dashboard.tsx              # 메인 대시보드(헤더, 업로드, 기록 목록 통합)
│   │   │   ├── AnalysisHistory.tsx        # 분석 기록 테이블, 검색, 필터, 편집, 삭제
│   │   │   ├── Viewer3D.tsx               # 3D 사고 복원 뷰어
│   │   │   ├── LoginScreen.tsx            # 로그인 화면
│   │   │   │
│   │   │   ├── figma/                     # Figma export 보조 컴포넌트
│   │   │   │   └── ImageWithFallback.tsx
│   │   │   │
│   │   │   └── ui/                        # shadcn/ui 컴포넌트 모음
│   │   │       ├── alert-dialog.tsx       # 삭제 확인 다이얼로그
│   │   │       ├── button.tsx
│   │   │       ├── input.tsx
│   │   │       ├── select.tsx
│   │   │       ├── table.tsx
│   │   │       └── ...                    # 40여 개 UI primitive
│   │   │
│   │   └── pages/
│   │       └── OAuthCallback.tsx          # OAuth 인증 후 토큰 처리
│   │
│   ├── context/
│   │   └── AuthContext.tsx                # 인증 상태, 토큰 관리, 자동 재발급
│   │
│   ├── lib/
│   │   └── apiClient.ts                   # axios 인스턴스, JWT 인터셉터, 401 재시도
│   │
│   ├── styles/
│   │   ├── index.css                      # 글로벌 진입 CSS
│   │   ├── tailwind.css                   # Tailwind base
│   │   ├── theme.css                      # 디자인 토큰
│   │   ├── calendar.css                   # 날짜 피커 스타일
│   │   └── fonts.css                      # 폰트 정의
│   │
│   └── main.tsx                           # React 진입점
│
├── index.html
├── package.json
├── vite.config.ts
├── postcss.config.mjs
└── .env.example
```

---

## 실행 방법

```bash
cd frontend
pnpm install
cp .env.example .env       # VITE_API_BASE_URL 설정
pnpm dev                   # http://localhost:5173
```

빌드:

```bash
pnpm build
pnpm preview
```

---

---

## 브랜치 전략

```text
main
└─ frontend
   ├─ feature/initial-app           로그인, 대시보드, 업로드, 기록 목록
   ├─ feature/3d-viewer             Gaussian Splat 뷰어 + 궤적 + 충돌 속도
   ├─ feature/delete-record         분석 기록 삭제 + 확인 다이얼로그
   └─ feature/server-side-search    영상명 검색을 서버사이드로 전환
```

기능 단위로 feature 브랜치를 분기하고, `frontend` 통합 브랜치에 PR로 머지한 뒤 최종적으로 `main` 으로 합칩니다.
