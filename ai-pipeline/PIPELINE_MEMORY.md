# Final Pipeline Memory

## [STEP 1] Input (Video)
IN: 교통사고 영상 (.mp4 / .avi)

## [STEP 2] Frame Extraction
IN: .mp4 영상

처리 A (COLMAP용)
ffmpeg → 10~15fps 추출 → 60km/h 기준 프레임 간 이동거리 ~1m → 특징점 매칭 안정적 확보

처리 B (3DGS 학습용)
COLMAP 완료 후 포즈 있는 프레임 중 5~10fps로 서브샘플링

OUT A: 이미지 시퀀스 (.jpg × N, COLMAP용)
OUT B: 이미지 서브셋 (.jpg × M, 3DGS용)

오픈소스: ffmpeg / LGPL

## [STEP 3] Object Segmentation + Tracking + 상태 제어
IN: 이미지 시퀀스 (OUT A)

처리
1) YOLOv8-seg (Instance Segmentation)
차량(car, truck, bus, motocycle, bicycle) 및 보행자(person) 클래스 탐지
픽셀 단위 폴리곤 마스크 및 BBox 생성
일반 YOLOv8 바운딩박스 마스킹만 쓰면 도로/건물까지 제거되어 COLMAP 실패 위험

2) ByteTrack
프레임 간 동일 차량 track_id 부여

3) Ego-motion 보상 (직접 구현)
배경(건물, 차선 등)의 Optical Flow로 카메라 순수 이동량 추정
객체 이동량에서 빼줌 (내 차와 동일 속도 차량을 정지 객체로 오인 방지)

4) 상태 역전파 (State Back-propagation) (직접 구현)
단 1프레임이라도 움직임(상대 속도 > 0) 감지된 객체는 전 구간 Dynamic으로 강제 분류

OUT
track_id별 바운딩박스 시퀀스 (.json)
픽셀 단위 segmentation 마스크 (.png × N, 흰색=dynamic, 검정=static)
마스크 이미지는 원본을 덮어쓰지 않고 별도 .png로 저장

오픈소스: YOLOv8-seg / AGPL-3.0
오픈소스: ByteTrack / MIT
직접 구현: Ego-motion 보상, 상태 역전파

## [STEP 3.5] User Targeting (사용자 선택)
IN: STEP 3 결과가 오버레이된 영상 UI (객체별 Bounding Box 및 ID 번호 표시)

처리: 사용자 목적에 맞춰 아래 옵션 중 하나 선택
옵션 A) 타겟 지정 모드 (Targeted Mode)
사고 당사자 차량(예: ID 15, ID 22)만 클릭 지정

옵션 B) 전체 시뮬레이션 모드 (Full Scene Mode)
Dynamic으로 분류된 모든 차량을 타겟으로 강제 할당

OUT: Target_IDs
옵션 A는 선택된 특정 차량 ID 리스트
옵션 B는 인식된 전체 동적 차량 ID 리스트

선택 UI 후보
영상에서 마우스 클릭
객체 누끼만 보이게 해서 클릭
track_id 키보드 입력

## [STEP 4] 카메라 포즈 추정 + Sparse PC 생성
IN
원본 이미지 시퀀스 (.jpg × N)
동적 객체 마스크 이미지 (.png × N)

처리: COLMAP 실행
ImageReader.mask_path 옵션 사용
마스크 영역 특징점 추출 건너뜀
정적 배경만 보고 안정적 포즈 추정
카메라 intrinsic 자동 추정
삼각측량으로 Sparse PC 생성

OUT
카메라 포즈 (SE(3) 4x4 행렬 × N)
카메라 intrinsic (초점거리, 주점)
Sparse PC (.ply, 수천~수만 점)

오픈소스: COLMAP / BSD

참고: STEP 3.5와 병행 가능

## [STEP 5] Monocular Depth 추정
이유: COLMAP Sparse PC는 텍스처 없는 영역(도로, 하늘, 벽면)에 빈틈이 많음

IN: 원본 이미지 시퀀스 (.jpg × N, 마스크 없는 원본)

처리: Depth Anything V2 실행 → 픽셀별 상대 깊이값 추정

OUT: depth map × N (상대적 깊이, 0~1)

오픈소스: Depth Anything V2
Small 모델: Apache-2.0 (제한 없음)
Large 모델: CC-BY-NC-4.0 (비상업용)

실행 시점 옵션
선택 1) STEP 3과 병렬 실행 (GPU 분할)
장점: STEP 3.5 시점에 STEP 5도 완료되어 뷰어까지 빠름
단점: 테스트 업로드 후 이탈 시 GPU 낭비
선택 2) 현재대로 순차 실행

## [STEP 6] Scale Alignment (절대 m 단위 변환)
IN
depth map × N (상대적 깊이)
COLMAP Sparse PC (up-to-scale)
물리적 prior: 카메라 높이 1.5m 가정

처리
1) 1차 정렬: COLMAP 기준 선형 회귀
Sparse PC 점을 depth map에 투영해 대응 쌍 생성 (예: (10, 0.8))
선형 회귀로 scale/shift 계산 (y = s x + t)
COLMAP 스케일에 맞춘 depth map 생성 (절대 단위 아님)

2) 2차 보정: 물리적 prior 주입
보정 depth map에서 도로(지면) 픽셀 추출
도로 픽셀들의 3D Y좌표 계산
카메라 원점과 Y축 거리 = 1.5m가 되도록 최종 scale 상수 적용

OUT: 절대 스케일 depth map (단위: m)

직접 구현
참고: 평면 방정식 기반 지면 추정

## [STEP 7] Dense Point Cloud 생성
이유: depth map은 2D이므로 3DGS 입력(Dense PC)로 변환 필요

IN
절대 스케일 depth map × N
카메라 포즈 (COLMAP)
카메라 intrinsic (초점거리, 주점)

처리
각 픽셀을 depth + intrinsic으로 3D 좌표 역투영
카메라 포즈로 world 좌표계 변환
전 프레임 누적

OUT: Dense PC (.ply, 수십~수백만 점)

직접 구현

## [STEP 8] Dense PC 노이즈 필터링
IN: Dense PC (아웃라이어 포함)

처리: Open3D Statistical Outlier Removal

OUT: 정제된 Dense PC (.ply)

오픈소스: Open3D / MIT

## [STEP 9] 차량 3D 궤적 변환
이유: 배경 복원과 별개로 최종 뷰어에서 차량 궤적 시각화 필요

IN
track_id (STEP 3.5)
track_id별 바운딩박스 시퀀스 및 마스크 (STEP 3)
절대 스케일 depth map (STEP 6)
카메라 포즈 및 intrinsic (STEP 4)

처리 (선택된 타겟만)
1) ROI 설정: 차량 마스크의 하단 40% 영역만 사용
바운딩박스 중심 1픽셀 depth 샘플링 방식 제거 (유리창으로 인한 튐 방지)
2) 기준점 추출: ROI 내 깊이값 하위 20~30% 분위수(Percentile)
가장 가까운 물리적 표면(차량 후미/뒷범퍼) 추정
3) intrinsic + 카메라 포즈로 3D 좌표 변환

OUT: track_id별 3D 궤적 (.json)
예: {차량A: [(x,y,z) × N], 차량B: ...}

직접 구현

## [STEP 10] 3DGS 학습
IN
원본 이미지 서브셋 (5~10fps)
동적 객체 마스크 이미지 (.png × M)
카메라 포즈 (COLMAP)
정제된 Dense PC (LiDAR 대체)

처리: gaussian-splatting
초기화: Dense PC로 교체 (학습 속도 향상)
마스크 Loss 제외 로직 추가
타겟 차량뿐만 아니라 사고와 무관한 모든 달리는 차량 및 보행자의 마스크 영역을 역전파에서 제외
Floater 현상 방어
Gaussian 위치/크기/색상/투명도 최적화

OUT: output.ply (동적 객체가 제거된 3D 배경)

오픈소스: gaussian-splatting / Inria (비상업)
직접 구현: 마스크 Loss 제외 로직

## [STEP 11] 포맷 변환
이유: 웹 뷰어 구동을 위해 용량 및 구조 최적화

IN: output.ply

처리: splat-converter

OUT: output.splat

오픈소스: splat-converter / MIT

## [STEP 12] 웹 뷰어 시각화 (Three.js 통합)
IN
output.splat (배경)
Target 차량 3D 궤적 (.json)

처리
배경 렌더링: WebGL 기반 .splat 렌더링, 다각도 시점 조작 지원
타겟 차량 오버레이
궤적(.json) 기반 더미 차량 모델(.gltf) 위치 업데이트
방향 시각화: 다음 궤적 좌표를 향해 Three.js lookAt()으로 Heading 렌더링
보행자는 뷰어 시각화에서 제외 (현재 기준)

OUT: 최종 3D 교통사고 재구성 인터랙티브 뷰어
다각도 자유 시점 조작
차량 A/B 궤적 오버레이
사고 지점 마킹 (옵션)

오픈소스: gsplat.js + React / MIT

## Pipeline Branch Summary
Track A (배경 복원): STEP 1 → 2 → 3 → 4 → 6 → 7 → 8 → 10 → 11 → 12
Track B (궤적 추출): STEP 1 → 2 → 3 → 3.5 → 4 → 6 → 9 → 12

