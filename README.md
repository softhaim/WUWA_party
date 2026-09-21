# Resonance Lab

명조: 워더링 웨이브의 보유 캐릭터와 육성 상태를 기록하고, 계정 전체에서 만들 수 있는 고점 파티를 배분하는 웹 앱입니다. Windows, macOS, Linux에서 파티 플래너를 사용할 수 있으며 로컬 AI 가이드는 실행 환경에 맞는 백엔드를 자동으로 선택합니다.

## 주요 기능

- 보유 여부, 공명 체인, 레벨, 육성 상태, 전용 무기와 재련 저장
- 속성·무기·레어도·역할 필터와 고해상도 일러스트·Live2D 보기
- 레벨 `MAX 90`, 육성 입력 시 자동 보유 처리
- 캐릭터별 최대 사용 횟수와 방랑자 속성 폼의 공유 사용 횟수 처리
- 메타 조합, 육성도, 돌파, 전용 무기와 대체 파츠를 반영한 복수 파티 배분
- 같은 보유풀에서 추천 구성 A/B/C 비교
- 보유풀과 추천 결과를 근거로 답하는 로컬 AI 육성 가이드

## 메인 화면
<img width="1539" height="983" alt="스크린샷 2026-09-21 오후 5 01 17" src="https://github.com/user-attachments/assets/d35a3fb8-6891-4b36-a050-c14363ef6222" />

## 파티 추천
<img width="1539" height="983" alt="스크린샷 2026-09-21 오후 5 01 40" src="https://github.com/user-attachments/assets/601039e9-91cc-4281-a49f-06bd55b0377a" />

## AI 가이드
<img width="1539" height="983" alt="스크린샷 2026-09-21 오후 5 02 46" src="https://github.com/user-attachments/assets/eb5fc13b-486e-47ac-8e98-1ac810218651" />

## 빠른 시작

Python 3.11 이상이 필요합니다. 파티 플래너만 사용할 때는 외부 패키지가 필요하지 않습니다.

```bash
git clone https://github.com/softhaim/WUWA_party.git
cd WUWA_party
python3 server.py
```

Windows에서는 `python3` 대신 `py`를 사용할 수 있습니다. 실행 후 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 열면 됩니다. 캐릭터 설정은 `roster.db`에 저장됩니다.

## AI 육성 가이드 설치

동일한 웹 UI와 API를 사용하며 운영체제에 따라 다음 백엔드가 선택됩니다.

| 환경 | 자동 선택 백엔드 | 학습 어댑터 |
|---|---|---|
| Apple Silicon Mac | MLX 4-bit | MLX LoRA |
| Windows/Linux + NVIDIA GPU | Transformers 4-bit CUDA | PEFT LoRA |
| Windows/Linux CPU | Transformers CPU | PEFT LoRA, 실행 가능하지만 느리고 메모리 사용량이 큼 |

[AI 모델 번들 다운로드](https://drive.google.com/file/d/1R_FOSyqjrUKm0ZYhfkTgQzqzOjQMx_Ls/view?usp=sharing)는 모든 환경에서 같은 파일을 사용합니다. 설치기는 현재 운영체제에 필요한 파일만 복사하고 MLX LoRA를 PEFT 형식으로도 변환합니다. 현재 링크의 번들에 Transformers 기본 모델이 없으면 Windows/Linux 설치 과정에서 Hugging Face 모델을 한 번 내려받습니다.

### Apple Silicon Mac

```bash
python3 -m venv .venv-ai
.venv-ai/bin/python -m pip install -r requirements-ai-mlx.txt
.venv-ai/bin/python scripts/install_model_bundle.py ~/Downloads/resonance-qwen3-4b-mlx-runtime.zip
.venv-ai/bin/python server.py
```

### Windows/Linux + NVIDIA GPU

먼저 [PyTorch 설치 선택기](https://pytorch.org/get-started/locally/)에서 GPU와 CUDA 버전에 맞는 PyTorch 명령을 실행합니다. 이어서 다음 명령을 사용합니다.

```powershell
py -m venv .venv-ai
.venv-ai\Scripts\activate
python -m pip install -r requirements-ai-transformers.txt
python scripts\install_model_bundle.py "%USERPROFILE%\Downloads\resonance-qwen3-4b-mlx-runtime.zip"
python scripts\download_local_model.py --backend transformers
python server.py
```

Linux에서는 같은 PyTorch 설치 후 다음 명령을 사용합니다.

```bash
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-ai-transformers.txt
python scripts/install_model_bundle.py ~/Downloads/resonance-qwen3-4b-mlx-runtime.zip
python scripts/download_local_model.py --backend transformers
python server.py
```

CUDA가 있으면 4-bit로 로드하고, 없으면 CPU로 실행합니다. CPU 모드는 Qwen3 4B 전체 가중치를 메모리에 올리므로 16GB 이상 RAM을 권장합니다.

### 번들 없이 모델 받기

운영체제를 자동 감지해 호환되는 기본 모델을 받습니다.

```bash
python scripts/download_local_model.py
```

`RESONANCE_BACKEND=mlx` 또는 `RESONANCE_BACKEND=transformers` 환경 변수로 자동 선택을 덮어쓸 수 있습니다.

## 직접 학습하기

### Apple Silicon MLX

```bash
.venv-ai/bin/python scripts/build_chat_dataset.py
.venv-ai/bin/python scripts/train_chatbot.py
```

### Windows/Linux NVIDIA CUDA

```powershell
python -m pip install -r requirements-ai-cuda.txt
python scripts\build_chat_dataset.py
python scripts\train_chatbot_cuda.py
```

CUDA 학습 결과는 `local_ai/adapters/qwen3-4b-cuda/`에 PEFT 형식으로 저장되며, 다음 웹 서버 실행부터 Transformers 백엔드가 자동으로 사용합니다. 별도 병합이나 변환이 필요하지 않습니다.

MLX로 학습한 어댑터를 Windows/Linux에서 사용하려면 다음 변환기를 사용할 수 있습니다. 모델을 재학습하지 않고 행렬 전치와 키 변환만 수행합니다.

```bash
python scripts/convert_mlx_adapter_to_peft.py
```

학습 과정은 터미널과 다음 로컬 파일에서 확인할 수 있습니다.

- `local_ai/runs/<실행 시각>/training.log`
- `local_ai/runs/<실행 시각>/metrics.jsonl`
- `local_ai/runs/<실행 시각>/report.html`

## 배포 번들 만들기

현재 준비된 백엔드만 자동으로 묶습니다.

```bash
python scripts/package_model_bundle.py
```

MLX와 Transformers 기본 모델을 모두 내려받은 뒤 완전한 멀티 플랫폼 오프라인 번들을 만들 수도 있습니다.

```bash
python scripts/download_local_model.py --backend all
python scripts/package_model_bundle.py --runtime universal
```

생성 파일은 `local_ai/dist/resonance-qwen3-4b-runtime.zip`입니다. 범용 번들은 두 모델 형식을 모두 포함하므로 용량이 큽니다. 일반 배포에서는 하나의 ZIP과 플랫폼별 자동 다운로드 방식을 권장합니다.

## 테스트

```bash
python3 -m unittest discover -s tests -v
```

테스트에는 파티 배분 경계값, 사용 횟수, 방랑자 공유 슬롯, 저장, 챗봇 문맥, 운영체제별 백엔드 선택과 MLX→PEFT 변환 검사가 포함됩니다.

## 프로젝트 구조

- `server.py` — 웹 서버, SQLite 저장, 파티 추천 엔진과 API
- `local_chatbot.py` — 질문 조건 해석과 MLX/Transformers 추론 백엔드
- `data/` — 캐릭터 카탈로그와 검증된 메타 파티
- `static/` — 웹 UI와 캐릭터 이미지
- `scripts/` — 데이터 생성, 모델 다운로드, 학습, 변환과 번들 도구
- `local_ai/` — 학습 설정, 데이터셋과 LoRA 어댑터
- `tests/` — 추천 엔진과 웹 앱 회귀 테스트

학습 구조와 파일 형식은 [local_ai/README.md](local_ai/README.md)에서 더 자세히 확인할 수 있습니다.

## 데이터와 라이선스

캐릭터 이미지와 Live2D 경로는 Nanoka의 공개 정적 데이터를 기반으로 로컬에 저장해 사용합니다. 파티 추천은 `data/team_rules.json`의 메타 조합과 앱에 입력한 보유·육성 정보를 함께 계산합니다.

기본 언어 모델은 Apache-2.0 라이선스의 [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)과 [MLX 4-bit 변환본](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)를 사용합니다.
