# 로컬 AI 폴더 안내

이 폴더에는 데이터셋, 학습 설정, 기본 모델, LoRA 어댑터, 실행별 로그가 역할별로 분리되어 있습니다.

## 한눈에 보는 흐름

```text
data/*.json
   └─ scripts/build_chat_dataset.py
        └─ local_ai/dataset/{train,valid,test}.jsonl
             ├─ Mac: scripts/train_chatbot.py → MLX QLoRA
             └─ CUDA: scripts/train_chatbot_cuda.py → Transformers + PEFT QLoRA

기본 모델(고정) + LoRA 어댑터(학습됨)
   └─ local_chatbot.py의 LocalChatbot._load()
        └─ 웹 앱 /api/chat
```

## 폴더별 의미

| 경로 | 내용 | Git 포함 |
|---|---|---|
| `configs/` | Mac MLX 및 CUDA 학습 하이퍼파라미터 | 예 |
| `dataset/` | 앱 데이터로 생성한 train/valid/test JSONL | 예 |
| `models/` | 약 2.3GB의 Qwen3 4B MLX 4-bit 기본 모델 | 아니요 |
| `adapters/qwen3-4b-mlx/` | 서비스가 쓰는 Mac용 학습 LoRA | 예 |
| `adapters/qwen3-4b-cuda/` | NVIDIA에서 만든 PEFT LoRA | 선택 |
| `runs/<시각>-mlx-qwen3-4b/` | 실행별 설정·원문 로그·손실·W&B·HTML 보고서 | 아니요 |

`models/`와 `runs/`가 Git에서 제외되는 이유는 각각 용량이 크고 실행할 때마다 새 파일이 생기기 때문입니다. 로컬 파일은 실제로 이 폴더 안에 남습니다.

## `_load()`가 하는 일

`mlx_lm.load()`는 MLX-LM의 기본 로더입니다. 첫 번째 인자로 4-bit 기본 모델을 읽습니다. `adapter_path`를 함께 주면 `adapter_config.json`에 따라 LoRA 층을 재구성하고 `adapters.safetensors`의 학습된 변화량을 결합합니다.

따라서 서비스 모델은 다음 두 파일 묶음입니다.

1. `models/qwen3-4b-instruct-2507-mlx-4bit/`: 원본 언어 능력, 4B 기본 가중치, 학습 중 고정
2. `adapters/qwen3-4b-mlx/`: 명조 답변 스타일을 배운 작은 LoRA 가중치, 학습 대상

LoRA만으로는 실행할 수 없고 항상 호환되는 기본 모델이 필요합니다. `_load()`가 지연 실행되는 이유는 캐릭터 목록만 보는 동안 수 GB의 통합 메모리를 점유하지 않기 위해서입니다.

## Mac에서 학습하기

```bash
.venv-ai/bin/python scripts/download_local_model.py
.venv-ai/bin/python scripts/train_chatbot.py
```

W&B는 이 규모의 로컬 실험에 필수적이지 않으므로 기본값이 `disabled`입니다. 기본 실행도 `training.log`, `metrics.jsonl`, `report.html`을 모두 남깁니다. 비교 실험이 많아져 W&B가 필요할 때만 다음처럼 명시적으로 켭니다.

```bash
.venv-ai/bin/python -m pip install -r requirements-ai-tracking.txt
.venv-ai/bin/wandb login
.venv-ai/bin/python scripts/train_chatbot.py --wandb-mode online
# 계정 연결 없이 W&B 형식만 남기려면:
.venv-ai/bin/python scripts/train_chatbot.py --wandb-mode offline
```

W&B 인증은 `wandb login`을 통해 사용자 환경에 보관되며, API 키는 저장소 파일에 포함하지 않습니다.

학습 중 터미널에 loss가 흐르고 동시에 다음 파일이 생성됩니다.

- `training.log`: MLX 전체 출력
- `metrics.jsonl`: train/validation/test loss와 peak memory 구조화 기록
- `run.json`: 모델·백엔드·시작/종료·성공 여부
- `config.snapshot.yaml`: 해당 실행이 실제 사용한 설정 사본
- `report.html`: W&B 로그인 없이 보는 로컬 손실 그래프

성공한 실행만 `adapters/qwen3-4b-mlx/`로 복사되어 다음 서버 재시작 때 적용됩니다.

## Google Drive 배포 번들 만들기

학습된 모델을 실행용 ZIP으로 묶을 때는 다음 명령을 사용합니다.

```bash
.venv-ai/bin/python scripts/package_model_bundle.py
```

생성되는 `local_ai/dist/resonance-qwen3-4b-mlx-runtime.zip` 하나를 Google Drive에 업로드하면 됩니다. ZIP에는 아래 두 폴더와 무결성 확인용 manifest만 들어갑니다.

```text
models/qwen3-4b-instruct-2507-mlx-4bit/
  config.json, tokenizer 파일들, model.safetensors 등
adapters/qwen3-4b-mlx/
  adapter_config.json, adapters.safetensors
bundle-manifest.json
```

다음 파일은 업로드하지 않습니다.

- `dataset/`: 학습 데이터
- `runs/`: 손실 로그와 W&B 실행 기록
- `roster.db`: 개인 보유 캐릭터 정보
- `.venv-ai/`: 현재 Mac에 종속된 가상환경
- API 키나 `.env` 파일

사용자는 Google Drive에서 ZIP을 받은 뒤 다음 명령만 실행합니다.

```bash
.venv-ai/bin/python scripts/install_model_bundle.py ~/Downloads/resonance-qwen3-4b-mlx-runtime.zip
```

설치기는 ZIP 경로 침범을 차단하고 모든 파일의 SHA-256을 확인한 뒤 `local_ai/models/`와 `local_ai/adapters/`에 설치합니다. 공개 배포라면 기반 모델의 Apache-2.0 라이선스와 모델 카드도 함께 안내하는 것이 좋습니다.

## Windows/Linux NVIDIA에서 학습하기

MLX는 Apple Silicon 전용입니다. CUDA PC에서는 PyTorch를 PC의 CUDA 버전에 맞춰 먼저 설치하고 다음을 실행합니다.

```powershell
py -m venv .venv-ai-cuda
.venv-ai-cuda\Scripts\pip install -r requirements-ai-cuda.txt
.venv-ai-cuda\Scripts\python scripts\build_chat_dataset.py
.venv-ai-cuda\Scripts\python scripts\train_chatbot_cuda.py
```

CUDA 경로는 원본 `Qwen/Qwen3-4B-Instruct-2507`을 4-bit NF4로 메모리에 올리고 PEFT LoRA를 학습합니다. 결과는 PEFT 형식이라 MLX 어댑터와 파일 호환되지 않습니다. Windows 서비스에 배포할 때는 Transformers/PEFT 추론 백엔드가 필요합니다.

## loss 읽는 법

- `train loss`: 훈련 예제에 대한 오차. 내려가는 것이 정상입니다.
- `validation loss`: 학습하지 않은 검증 예제의 오차. 이 값이 다시 오르면 과적합 신호입니다.
- `test loss`: 설정을 고른 뒤 마지막에 한 번 확인하는 별도 테스트셋 오차입니다.
- `perplexity`: `exp(test loss)`. 낮을수록 해당 정답 문장을 덜 낯설어합니다.

loss 하나만으로 실제 답변 품질을 보장할 수는 없습니다. 파티 정확성은 Python 추천 엔진 회귀 테스트를 함께 통과해야 합니다.
