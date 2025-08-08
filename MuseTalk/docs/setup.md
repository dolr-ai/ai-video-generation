cd ai-video-generation/
bash just_uv.sh --py3.10
source .venv/bin/activate
cd MuseTalk/
bash download_weights_with_venv.sh
uv pip install -r requirements.txt

uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
<!-- uv pip install "numpy<2" -->
<!-- uv pip install mmcv==2.0.1 -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.1/index.html -->

<!-- use cpu version of mmcv -->
uv pip install mmcv==2.0.1 --no-build-isolation --no-cache-dir -f https://download.openmmlab.com/mmcv/dist/cpu/torch2.0/index.html
uv pip install mmdet==3.1.0
uv pip install mmpose==1.1.0
uv pip install tensorrt[cuda12]

wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
tar -xf ffmpeg-master-latest-linux64-gpl.tar.xz

export FFMPEG_PATH="$(realpath ./ffmpeg-master-latest-linux64-gpl)"


python -m scripts.inference --inference_config ./configs/inference/test.yaml --result_dir ./results/test --unet_model_path ./models/musetalkV15/unet.pth --unet_config ./models/musetalkV15/musetalk.json --version v15 --ffmpeg_path $FFMPEG_PATH/bin