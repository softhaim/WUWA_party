# 로컬 AI 기술 참고

메인 설치 방법은 프로젝트 [README](../README.md)를 참고하세요. 이 문서는 모델·LoRA 파일과 학습/추론 백엔드의 관계를 설명합니다.

## 처리 흐름

```text
data/*.json
  └─ build_chat_dataset.py
       └─ dataset/{train,valid,test}.jsonl
            ├─ Apple Silicon: MLX QLoRA → adapters/qwen3-4b-mlx
            └─ NVIDIA CUDA: PEFT QLoRA → adapters/qwen3-4b-cuda

local_chatbot.py
  ├─ Apple Silicon → mlx_lm + MLX LoRA
  └─ Windows/Linux → Transformers + PEFT LoRA
```

## 폴더별 의미

| 경로 | 내용 | Git 포함 |
|---|---|---|
| `configs/` | MLX/CUDA 학습 하이퍼파라미터 | 예 |
| `dataset/` | train/valid/test JSONL | 예 |
| `models/qwen3-4b-instruct-2507-mlx-4bit/` | Apple Silicon용 MLX 4-bit 기본 모델 | 아니요 |
| `models/qwen3-4b-instruct-2507-hf/` | Transformers용 Hugging Face 기본 모델 | 아니요 |
| `adapters/qwen3-4b-mlx/` | MLX LoRA | 예 |
| `adapters/qwen3-4b-cuda/` | Transformers PEFT LoRA | 예 |
| `runs/` | 실행별 로그, loss, 설정 사본과 HTML 보고서 | 아니요 |

기본 모델은 용량 때문에 Git에서 제외합니다. LoRA만으로는 실행할 수 없으며 반드시 호환되는 기본 모델과 함께 사용합니다.
`scripts/install_model_bundle.py`는 ZIP을 검증해 이 구조로 복사하고, 현재 운영체제용 기본 모델이 ZIP에 없으면 Hugging Face에서 자동으로 준비합니다. 모델·어댑터·필수 패키지 중 하나가 없으면 `/api/ai/status`와 웹 AI 가이드가 설치 필요 상태를 표시합니다.
가장 간단한 방법은 번들 ZIP을 압축 해제하지 않고 `local_ai/bundles/`에 넣은 뒤 `python scripts/install_model_bundle.py`를 실행하는 거예요. 다른 위치에 보관하려면 `python scripts/install_model_bundle.py <ZIP의 실제 경로>`처럼 경로를 직접 지정할 수도 있어요.

## 추론 백엔드

`local_chatbot.detect_backend()`는 Apple Silicon에서 `mlx`, 그 밖의 환경에서 `transformers`를 선택합니다. `RESONANCE_BACKEND`로 강제 선택할 수 있습니다.

### MLX

`mlx_lm.load(model, adapter_path=...)`가 4-bit 기본 모델 위에 `adapters.safetensors`의 변화량을 적용합니다. 모델은 첫 AI 질문이 들어올 때 지연 로딩됩니다.

### Transformers/PEFT

CUDA가 있으면 `bitsandbytes` NF4 4-bit로 기본 모델 전체를 지정 GPU에 고정하고, `PeftModel.from_pretrained()`가 `adapter_model.safetensors`를 적용합니다. CUDA 학습기의 출력 폴더가 곧 서비스 입력 폴더이므로 추가 병합은 필요하지 않습니다. `device_map="auto"`에 의한 RAM 오프로딩은 사용하지 않으며, CUDA가 없으면 기본적으로 오류를 표시합니다. CPU 모드는 `RESONANCE_ALLOW_CPU=1`을 지정한 경우에만 허용합니다.

Windows/Linux에서는 서버 실행 전에 `python scripts/check_ai_runtime.py`로 PyTorch CUDA 빌드, GPU 이름, bitsandbytes와 모델/어댑터 존재 여부를 한 번에 확인할 수 있습니다.

## MLX LoRA를 PEFT로 변환

두 라이브러리는 같은 LoRA 개념을 사용하지만 행렬 방향과 파일 키가 다릅니다.

```bash
python scripts/convert_mlx_adapter_to_peft.py
```

변환기는 MLX의 `(input, rank)` / `(rank, output)` 행렬을 PEFT의 `(rank, input)` / `(output, rank)`로 전치하고 키를 바꿉니다. 기본 모델 가중치는 수정하지 않습니다. 번들 설치기도 PEFT 어댑터가 없으면 같은 변환을 자동으로 실행합니다.

## 학습 결과 확인

MLX 학습은 터미널 출력과 함께 다음 파일을 남깁니다.

- `training.log`: 전체 출력
- `metrics.jsonl`: train/validation/test loss와 peak memory
- `run.json`: 모델, 플랫폼, 시작·종료와 성공 여부
- `config.snapshot.yaml`: 실제 사용한 설정
- `report.html`: 로컬 손실 그래프

성공한 실행만 서비스 어댑터 폴더로 복사됩니다. CUDA 학습은 `Trainer` 로그와 `test_metrics.json`을 PEFT 출력 폴더에 저장합니다.
2026-09-25 MLX 재학습 실행은 validation loss `4.336 → 2.937`, test loss `3.142`, test perplexity `23.149`를 기록했습니다. 실행별 수치는 Git에 포함되지 않는 `runs/` 보고서를 기준으로 확인하세요.

## 배포 ZIP

```bash
python scripts/package_model_bundle.py
```

`--runtime mlx`, `--runtime transformers`, `--runtime universal` 중 하나를 지정할 수 있습니다. `auto`는 현재 준비된 런타임을 모두 포함합니다. 범용 오프라인 ZIP은 두 기본 모델을 모두 포함해 용량이 크므로, 일반적으로는 공용 설치 ZIP과 플랫폼별 모델 다운로드를 함께 사용합니다.

ZIP에는 모델·어댑터·체크섬 manifest만 들어갑니다. 데이터셋, 학습 로그, `roster.db`, 가상환경과 비밀 정보는 포함되지 않습니다.

## loss 읽는 법

- `train loss`: 훈련 예제 오차
- `validation loss`: 학습하지 않은 검증 예제 오차
- `test loss`: 설정 선택 후 확인하는 테스트셋 오차
- `perplexity`: `exp(test loss)`

loss만으로 실제 파티 답변의 정확성을 보장할 수 없으므로 Python 추천 엔진 회귀 테스트도 함께 실행합니다.
