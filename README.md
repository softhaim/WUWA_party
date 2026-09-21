# Resonance Lab

명조: 워더링 웨이브의 보유 캐릭터와 육성 상태를 기록하고, 여러 파티를 계정 전체 기준으로 배분하는 웹 앱입니다. 설치 후 브라우저에서 캐릭터를 체크하면 파티 추천과 육성 가이드를 바로 사용할 수 있습니다.

## 주요 기능

- 캐릭터 보유 여부, 공명 체인, 레벨, 육성 상태, 전용 무기와 재련 저장
- 속성·무기·레어도·역할 필터와 고해상도 일러스트·Live2D 보기
- 레벨 `MAX 90`, 육성 입력 시 자동 보유 처리
- 캐릭터별 최대 사용 횟수와 방랑자 속성 폼의 공유 사용 횟수 처리
- 메타 조합, 육성도, 돌파, 전용 무기와 대체 파츠를 함께 고려한 복수 파티 배분
- 같은 보유풀에서 추천 구성 A/B/C 비교
- 보유풀과 추천 결과를 바탕으로 답하는 육성 가이드 챗봇

## 빠른 시작

### 파티 플래너만 사용하기

Python 3.11 이상이 설치되어 있다면 별도 패키지 없이 실행됩니다.

```bash
git clone https://github.com/softhaim/WUWA_party.git
cd WUWA_party
python3 server.py
```

브라우저에서 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 열면 됩니다. 캐릭터 설정은 프로젝트의 `roster.db`에 저장됩니다.

### AI 육성 가이드까지 사용하기 — Apple Silicon Mac

1. 프로젝트용 Python 환경과 AI 패키지를 준비합니다.

```bash
python3 -m venv .venv-ai
.venv-ai/bin/python -m pip install -r requirements-ai.txt
```

2. [AI 모델 번들 다운로드](https://drive.google.com/file/d/1R_FOSyqjrUKm0ZYhfkTgQzqzOjQMx_Ls/view?usp=sharing)에서 ZIP 파일을 내려받고 설치합니다.

```bash
.venv-ai/bin/python scripts/install_model_bundle.py \
  ~/Downloads/resonance-qwen3-4b-mlx-runtime.zip
```

3. AI 환경으로 서버를 실행합니다.

```bash
.venv-ai/bin/python server.py
```

번들에는 `Qwen3-4B-Instruct-2507 MLX 4-bit` 기본 모델과 이 프로젝트용 LoRA 어댑터가 함께 들어 있습니다. 설치기는 파일 체크섬을 확인한 뒤 `local_ai/models/`와 `local_ai/adapters/`에 배치합니다.

Google Drive 대신 Hugging Face에서 기본 모델을 직접 받을 수도 있습니다.

```bash
.venv-ai/bin/python scripts/download_local_model.py
```

저장소에 LoRA 어댑터가 있으면 자동으로 함께 적용됩니다.

## 직접 학습하기

캐릭터·파티 데이터를 수정한 뒤 자신만의 LoRA를 다시 학습할 수 있습니다.

```bash
.venv-ai/bin/python scripts/build_chat_dataset.py
.venv-ai/bin/python scripts/train_chatbot.py
```

학습 결과는 다음 위치에 정리됩니다.

- `local_ai/dataset/`: train / valid / test JSONL
- `local_ai/runs/<실행 시각>/`: 원본 로그, loss 기록, 설정 사본, HTML 보고서
- `local_ai/adapters/qwen3-4b-mlx/`: 서비스에 적용되는 최종 LoRA

W&B는 기본적으로 사용하지 않습니다. 여러 실험을 비교할 때만 선택 패키지를 설치하고 활성화할 수 있습니다.

```bash
.venv-ai/bin/python -m pip install -r requirements-ai-tracking.txt
.venv-ai/bin/wandb login
.venv-ai/bin/python scripts/train_chatbot.py --wandb-mode online
```

Windows/Linux NVIDIA GPU에서는 같은 데이터셋을 사용하는 CUDA 학습 코드가 제공됩니다.

```powershell
py -m venv .venv-ai-cuda
.venv-ai-cuda\Scripts\pip install -r requirements-ai-cuda.txt
.venv-ai-cuda\Scripts\python scripts\build_chat_dataset.py
.venv-ai-cuda\Scripts\python scripts\train_chatbot_cuda.py
```

CUDA 학습 결과는 PEFT 형식이며, 현재 웹 앱의 AI 추론 백엔드는 Apple Silicon용 MLX입니다.

## 모델 번들 만들기

학습한 모델을 다른 Mac에서 바로 사용할 수 있는 ZIP으로 묶을 수 있습니다.

```bash
.venv-ai/bin/python scripts/package_model_bundle.py
```

생성 파일:

```text
local_ai/dist/resonance-qwen3-4b-mlx-runtime.zip
```

번들에는 실행에 필요한 모델과 LoRA만 포함되며, 학습 로그·데이터셋·`roster.db`·가상환경은 포함되지 않습니다.

## 테스트

```bash
python3 -m unittest discover -s tests -v
```

테스트에는 파티 배분 경계값, 사용 횟수, 방랑자 공유 슬롯, 캐릭터 정렬, 저장과 챗봇 문맥 생성 검사가 포함됩니다.

## 프로젝트 구조

- `server.py` — 로컬 웹 서버, SQLite 저장, 파티 추천 엔진과 API
- `local_chatbot.py` — 질문 조건 해석, 추천 결과 검색, MLX 모델 추론
- `data/characters.json` — 캐릭터 카탈로그
- `data/team_rules.json` — 검증된 메타 파티와 호환성 데이터
- `static/` — 웹 UI와 로컬 캐릭터 이미지
- `scripts/` — 데이터 생성, 모델 다운로드, MLX/CUDA 학습, 모델 번들 도구
- `local_ai/` — AI 설정, 데이터셋과 LoRA
- `tests/` — 추천 엔진과 웹 앱 회귀 테스트

학습 구조, LoRA 로딩 방식과 파일별 설명은 [local_ai/README.md](local_ai/README.md)에서 더 자세히 확인할 수 있습니다.

## 데이터와 이미지

캐릭터 이미지와 Live2D 경로는 Nanoka의 공개 정적 데이터를 기반으로 로컬에 저장해 사용합니다. 파티 추천은 `data/team_rules.json`의 메타 조합과 앱에 입력한 보유·육성 정보를 함께 계산합니다.

기본 언어 모델은 Apache-2.0 라이선스의 [mlx-community/Qwen3-4B-Instruct-2507-4bit](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)를 사용합니다.
