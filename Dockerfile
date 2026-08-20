FROM nvidia/cuda:12.2.2-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-dev python3-pip \
    ffmpeg git wget \
    libgl1-mesa-glx libglib2.0-0 \
    cmake ninja-build \
    libboost-all-dev libeigen3-dev \
    libflann-dev libfreeimage-dev libmetis-dev \
    libgoogle-glog-dev libgtest-dev \
    libsqlite3-dev libglew-dev \
    qtbase5-dev libqt5opengl5-dev \
    libcgal-dev libceres-dev \
    && rm -rf /var/lib/apt/lists/*

# Build COLMAP with CUDA support (PTX for 89 enables JIT on newer GPUs like Blackwell)
RUN git clone https://github.com/colmap/colmap.git /tmp/colmap && \
    cd /tmp/colmap && git checkout 3.11.1 && \
    mkdir build && cd build && \
    cmake .. -GNinja -DCMAKE_CUDA_ARCHITECTURES="86;89" && \
    ninja -j$(nproc) && ninja install && \
    rm -rf /tmp/colmap

# PyTorch with CUDA (install before requirements.txt to avoid CPU override)
WORKDIR /workspace
RUN pip3 install --no-cache-dir \
    torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu118

# Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir "numpy>=1.24,<2" && \
    pip3 install --no-cache-dir \
    --ignore-installed torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    -r requirements.txt && \
    pip3 install --no-cache-dir --no-build-isolation waymo-open-dataset-tf-2-12-0

# 3D Gaussian Splatting + CUDA extensions
# Set CUDA arch explicitly — Docker build has no GPU, so auto-detect fails.
# 86=Ampere(A100/3090), 89=Ada(4090/L40S). Adjust if your GPU differs.
ENV TORCH_CUDA_ARCH_LIST="8.6;8.9"
RUN git clone --recursive https://github.com/graphdeco-inria/gaussian-splatting.git \
        /workspace/third_party/gaussian-splatting && \
    cd /workspace/third_party/gaussian-splatting && \
    pip3 install --no-cache-dir submodules/diff-gaussian-rasterization && \
    pip3 install --no-cache-dir submodules/simple-knn && \
    pip3 install --no-cache-dir plyfile

# AB3DMOT (Stage 09 Kalman tracker). Non-commercial research license.
# .dockerignore excludes ai-pipeline/third_party/ so we clone it here.
RUN git clone --depth 1 https://github.com/xinshuoweng/AB3DMOT.git \
        /workspace/third_party/AB3DMOT
ENV AB3DMOT_ROOT=/workspace/third_party/AB3DMOT

# Copy project
COPY . .

ENTRYPOINT ["python3", "ai-pipeline/scripts/run_pipeline.py"]
