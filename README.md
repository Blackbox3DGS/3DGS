# 3D AI 블랙박스 (3D AI Blackbox) - 3DGS Module

## 🚗 프로젝트 개요
**3D AI 블랙박스**는 차량 사고 데이터를 3D로 시각화하여 사고 정황을 입체적으로 파악할 수 있게 돕는 프로젝트입니다. 
이 리포지토리는 그 핵심 모듈인 **Single-view 3D Reconstruction** 파트를 담당합니다. 
단 한 장의 2D 차량/도로 이미지만 입력하면, 즉시 3D Gaussian Splatting(3DGS) 모델(`.ply`)을 생성해냅니다.

### 🎯 핵심 목표
*   **Instant 3D**: LiDAR 없이 2D 이미지만으로 3D 형상 복원.
*   **Fast Inference**: 사고 현장에서 즉시 활용 가능한 빠른 추론 속도.
*   **Lightweight**: 무거운 장비 없이 일반 카메라(블랙박스, 스마트폰) 영상 활용.

---

## 🛠 현재 구현 상태 (Current Status)
현재 **Phase 1: 프로토타입** 단계가 완료되었습니다.

*   **기반 기술**: [Splatter Image (CVPR 2024)](https://github.com/szymanowiczs/splatter-image)
*   **구현 기능**:
    *   ✅ **Inference Pipeline**: `inference_splatter.py`를 통해 이미지 입력 → 3DGS 파라미터 추출 → PLY 저장 자동화.
    *   ✅ **Submodule Integration**: 공식 `splatter-image` 리포지토리를 서브모듈로 연동하여 최신 코드 베이스 유지.
    *   ✅ **Environment**: Mac(Apple Silicon) 환경에서도 추론 가능한 PyTorch 기반 파이프라인 구축 (CUDA 의존성 우회).

---

## 🚀 사용 방법 (Usage)

### 1. 환경 설정
```bash
# 가상환경 활성화
source ./venv/bin/activate

# 의존성 설치 (최초 1회)
pip install -r splatter-image/requirements.txt
```

### 2. 실행 (Inference)
준비된 차량 이미지와 사전 학습된 모델 체크포인트가 필요합니다.

```bash
python inference_splatter.py \
  --image ./data/car_accident.jpg \
  --output ./output/result.ply \
  --model ./checkpoints/model_cars.pth
```
생성된 `result.ply` 파일은 [Splat](https://splat.antimatter15.com/) 등의 뷰어에서 바로 확인할 수 있습니다.

---

## ⚠️ 현재의 한계 및 부족한 점 (Limitations)
1.  **배경 제거 미적용 (No Background Removal)**
    *   현재는 입력 이미지의 배경까지 포함하여 3D로 변환됩니다. 차량만 깔끔하게 객체화하기 위해 `rembg` 등을 활용한 전처리 과정 추가가 시급합니다.
2.  **Mac 렌더링 제한**
    *   `diff-gaussian-rasterization` 라이브러리의 CUDA 의존성으로 인해, 로컬 Mac 환경에서는 **파라미터 추출(.ply 생성)**만 가능하며, 실시간 렌더링이나 학습(Training)은 불가능합니다.
3.  **웹 뷰어 부재**
    *   생성된 3D 모델을 사용자가 웹에서 바로 돌려볼 수 있는 전용 뷰어가 없습니다. (현재는 외부 뷰어 사용 필요)

---

## 🗺 향후 계획 (Roadmap)

### Phase 2: 고도화 (Next Step)
- [ ] **배경 제거 (Background Removal)**: 입력 이미지에서 차량 누끼를 자동으로 따서 3D 변환 품질 향상.
- [ ] **웹 뷰어 연동**: Three.js 또는 WebGL 기반의 자체 3D 뷰어 페이지 개발.
- [ ] **자동화 스크립트**: 모델 다운로드 및 폴더 구조 세팅을 위한 `setup.sh` 작성.

### Phase 3: 확장 (Future)
- [ ] **사고 현장 재구성**: 차량뿐만 아니라 도로, 가드레일 등 주변 환경 3D 매핑.
- [ ] **멀티뷰 지원**: CCTV 등 여러 각도의 영상이 있을 경우 정합하여 정밀도 향상.
- [ ] **파인튜닝 (Fine-tuning)**: 실제 사고 데이터셋을 활용하여 파손된 차량에 특화된 모델 학습.

---

## 🤝 기여 가이드
*   `main` 브랜치는 배포용으로 유지합니다.
*   모든 개발은 **`develop`** 브랜치에서 진행해주세요.
