import torch
import os
import argparse
import numpy as np
from PIL import Image
from torchvision import transforms
import sys
from plyfile import PlyData, PlyElement
from omegaconf import OmegaConf

# =============================================================================
# [Environment Setup] 필수 라이브러리 및 경로 설정
# =============================================================================
# 현재 디렉토리의 'splatter-image' 폴더를 모듈 검색 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
splatter_image_dir = os.path.join(current_dir, 'splatter-image')
if splatter_image_dir not in sys.path:
    sys.path.append(splatter_image_dir)

try:
    from scene.gaussian_predictor import GaussianSplatPredictor
    from utils.general_utils import matrix_to_quaternion
except ImportError as e:
    print(f"Error importing Splatter Image modules: {e}")
    print(f"Make sure you have cloned the repository into {splatter_image_dir}")
    sys.exit(1)

# =============================================================================
# [Model Loading] 사전 학습된 모델 로드
# =============================================================================
def load_model(checkpoint_path, cfg_path=None, device='cuda'):
    """
    사전 학습된 Splatter Image 체크포인트를 로드합니다.
    """
    print(f"Loading model from {checkpoint_path}...")
    
    # 1. Config 로드
    # 기본 Config 로드 (splatter-image/configs/default_config.yaml)
    default_cfg_path = os.path.join(splatter_image_dir, 'configs', 'default_config.yaml')
    if os.path.exists(default_cfg_path):
        cfg = OmegaConf.load(default_cfg_path)
    else:
        print("Warning: Default config not found. Using empty config.")
        cfg = OmegaConf.create()

    # 사용자 지정 Config가 있으면 병합 (선택 사항)
    if cfg_path and os.path.exists(cfg_path):
        user_cfg = OmegaConf.load(cfg_path)
        cfg = OmegaConf.merge(cfg, user_cfg)
        
    # 모델 초기화에 필요한 설정 강제 주입 (필요시)
    # 예: cfg.model.network_with_offset = True 등
    # 체크포인트에 저장된 config가 있다면 그것을 쓰는게 가장 좋음.
    # 여기서는 기본값 사용.
    
    # 2. 모델 아키텍처 초기화
    model = GaussianSplatPredictor(cfg)
    
    # 3. 가중치 로드
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    # 체크포인트 구조 확인 및 로드
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'], strict=False)
    else:
        model.load_state_dict(checkpoint, strict=False)
        
    model.to(device)
    model.eval()
    return model, cfg

# =============================================================================
# [Image Preprocessing] 입력 이미지 전처리
# =============================================================================
def preprocess_image(image_path, target_size=128, device='cuda'):
    """
    이미지를 로드하고 리사이징 및 텐서 변환을 수행합니다.
    카메라 포즈가 없는 경우 기본 포즈(Canonical Pose)를 가정합니다.
    """
    print(f"Preprocessing image: {image_path}")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    img = Image.open(image_path).convert("RGB")
    
    # 리사이징 및 텐서 변환 (0~1 범위)
    transform = transforms.Compose([
        transforms.Resize((target_size, target_size)),
        transforms.ToTensor(),
    ])
    
    # (1, 3, H, W) - Batch size 1, Single View
    img_tensor = transform(img).unsqueeze(0).to(device) 
    
    # Canonical Camera Pose 생성
    # Splatter Image는 입력 이미지의 시점을 기준으로 3D를 생성하므로,
    # 입력 카메라를 원점(Identity)으로 가정할 수 있습니다.
    
    # View to World Matrix (4x4)
    # 여기서는 Identity 행렬을 사용합니다. (카메라가 월드 원점에 위치)
    view_to_world = torch.eye(4).unsqueeze(0).unsqueeze(0).to(device) # (B, N_views, 4, 4)
    
    # Quaternion for rotation (used for rotating predicted gaussians)
    # Identity rotation quaternion: [1, 0, 0, 0] (w, x, y, z) or [0, 0, 0, 1]?
    # utils.general_utils.matrix_to_quaternion 구현 확인 필요.
    # 보통 w, x, y, z 순서임.
    
    # Identity matrix의 quaternion 계산
    rotation_matrix = view_to_world[0, 0, :3, :3]
    quaternion = matrix_to_quaternion(rotation_matrix) # (4,)
    
    # (B, N_views, 4)
    source_cv2wT_quat = quaternion.unsqueeze(0).unsqueeze(0).to(device)
    
    return img_tensor, view_to_world, source_cv2wT_quat

# =============================================================================
# [Inference] 메인 추론 로직
# =============================================================================
def run_inference(model, img_tensor, view_to_world, source_cv2wT_quat):
    """
    모델에 이미지를 입력하여 3D Gaussian 파라미터를 예측합니다.
    """
    print("Running inference...")
    
    with torch.no_grad():
        # forward(self, x, source_cameras_view_to_world, source_cv2wT_quat=None, focals_pixels=None, activate_output=True)
        # focals_pixels는 CO3D 데이터셋(hydrants, teddybears)에서만 필요. Cars는 고정 초점거리 가정.
        outputs = model(
            img_tensor, 
            view_to_world, 
            source_cv2wT_quat=source_cv2wT_quat,
            activate_output=True
        )
        
    return outputs

# =============================================================================
# [Save to PLY] PLY 파일 저장
# =============================================================================
def save_ply(outputs, output_path):
    """
    추론된 가우시안 파라미터를 .ply 파일로 저장합니다.
    """
    print(f"Saving result to {output_path}...")
    
    # 텐서를 CPU numpy 배열로 변환
    # outputs는 (B, N_points, C) 형태
    
    xyz = outputs['xyz'][0].cpu().numpy() # (N, 3)
    opacity = outputs['opacity'][0].cpu().numpy() # (N, 1)
    scaling = outputs['scaling'][0].cpu().numpy() # (N, 3)
    rotation = outputs['rotation'][0].cpu().numpy() # (N, 4)
    features_dc = outputs['features_dc'][0].cpu().numpy() # (N, 1, 3) -> (N, 3)
    features_dc = features_dc.reshape(-1, 3)

    # 데이터 개수 확인
    num_points = xyz.shape[0]
    
    # PLY 구조 생성
    dtype = [('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
             ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
             ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
             ('opacity', 'f4'),
             ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
             ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4')]
    
    elements = np.empty(num_points, dtype=dtype)
    
    elements['x'] = xyz[:, 0]
    elements['y'] = xyz[:, 1]
    elements['z'] = xyz[:, 2]
    
    elements['nx'] = np.zeros(num_points)
    elements['ny'] = np.zeros(num_points)
    elements['nz'] = np.zeros(num_points)
    
    elements['f_dc_0'] = features_dc[:, 0]
    elements['f_dc_1'] = features_dc[:, 1]
    elements['f_dc_2'] = features_dc[:, 2]
    
    elements['opacity'] = opacity.flatten()
    
    elements['scale_0'] = scaling[:, 0]
    elements['scale_1'] = scaling[:, 1]
    elements['scale_2'] = scaling[:, 2]
    
    # Rotation: Splatter Image outputs might need normalization or reordering depending on viewer
    # Standard 3DGS PLY expects (w, x, y, z) or (x, y, z, w).
    # Splatter Image uses (w, x, y, z) internally (from matrix_to_quaternion).
    # Most viewers expect (w, x, y, z).
    elements['rot_0'] = rotation[:, 0] # w
    elements['rot_1'] = rotation[:, 1] # x
    elements['rot_2'] = rotation[:, 2] # y
    elements['rot_3'] = rotation[:, 3] # z
    
    # 파일 쓰기
    el = PlyElement.describe(elements, 'vertex')
    PlyData([el]).write(output_path)
    
    print("Done.")

# =============================================================================
# [Main] 메인 실행 함수
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Splatter Image Inference Script")
    parser.add_argument("--image", type=str, required=True, help="Input image path")
    parser.add_argument("--output", type=str, required=True, help="Output PLY file path")
    parser.add_argument("--model", type=str, required=True, help="Path to pretrained checkpoint")
    parser.add_argument("--config", type=str, default=None, help="Path to model config (optional)")
    parser.add_argument("--device", type=str, default="cuda", help="Device to run inference on")
    
    args = parser.parse_args()
    
    # 디바이스 설정
    if args.device == 'cuda' and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        device = torch.device("cpu")
    else:
        device = torch.device(args.device)
    
    # 1. 모델 로드
    model, cfg = load_model(args.model, args.config, device)
    
    # 2. 이미지 전처리
    target_size = cfg.data.training_resolution if hasattr(cfg, 'data') else 128
    img_tensor, view_to_world, source_cv2wT_quat = preprocess_image(args.image, target_size=target_size, device=device)
    
    # 3. 추론
    outputs = run_inference(model, img_tensor, view_to_world, source_cv2wT_quat)
    
    # 4. 결과 저장
    save_ply(outputs, args.output)

if __name__ == "__main__":
    main()
