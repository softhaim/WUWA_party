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

AI 가이드는 운영체제에 맞는 실행 백엔드를 자동 선택합니다. 모델이 없거나 실행 패키지가 빠져 있으면 웹의 AI 가이드 화면에 설치 안내가 표시되며, 캐릭터 관리와 파티 플래너는 그대로 사용할 수 있습니다.

| 환경 | 자동 선택 백엔드 | 학습 어댑터 |
|---|---|---|
| Apple Silicon Mac | MLX 4-bit | MLX LoRA |
| Windows/Linux + NVIDIA GPU | Transformers 4-bit CUDA | PEFT LoRA |
| Windows/Linux CPU | Transformers CPU | PEFT LoRA, 실행은 가능하지만 매우 느림 |

[AI 모델 번들 다운로드](https://drive.google.com/drive/folders/1TcNuDnVOnchhMmfK9phJ_TMabgfWhUC8?usp=sharing)

ZIP은 프로젝트 안의 특정 폴더에 둘 필요가 없습니다. `다운로드` 폴더처럼 사용자가 읽을 수 있는 아무 경로에 저장한 뒤, 그 ZIP의 실제 경로를 설치 명령 마지막 인자로 전달하면 됩니다. 아래 예시는 파일을 기본 다운로드 폴더에 저장하고 파일명을 `resonance-qwen3-4b-runtime.zip`으로 맞춘 경우입니다.

ZIP을 직접 풀지 마세요. 설치기가 체크섬을 검증한 뒤 압축 안의 파일을 프로젝트 기준으로 다음 위치에 알아서 배치합니다.

- 기본 모델: `local_ai/models/`
- 학습된 LoRA: `local_ai/adapters/`

예를 들어 `/Users/me/AI/model.zip`에 저장했다면 Mac/Linux에서는 `python scripts/install_model_bundle.py /Users/me/AI/model.zip`, Windows의 `D:\AI\model.zip`에 저장했다면 `python scripts\install_model_bundle.py "D:\AI\model.zip"`처럼 입력합니다. 경로에 공백이 있으면 반드시 따옴표로 감싸세요. 설치가 성공한 뒤에는 원본 ZIP을 다른 곳으로 옮기거나 삭제해도 실행에 영향이 없습니다.

현재 배포 ZIP이 MLX 기본 모델만 포함해도 학습 결과 자체는 다른 운영체제에서 사용할 수 있습니다. 설치기가 MLX LoRA를 Windows/Linux용 PEFT 형식으로 변환하고, 해당 플랫폼의 Transformers 기본 모델이 없으면 Hugging Face에서 자동으로 한 번 내려받습니다. 따라서 일반 설치에는 같은 ZIP을 쓰되 인터넷 연결이 필요할 수 있습니다. 인터넷 없이 모든 플랫폼에서 설치하려면 아래의 `universal` 번들을 사용해야 합니다.

### Apple Silicon Mac

```bash
python3 -m venv .venv-ai
.venv-ai/bin/python -m pip install -r requirements-ai-mlx.txt
.venv-ai/bin/python scripts/install_model_bundle.py ~/Downloads/resonance-qwen3-4b-runtime.zip
.venv-ai/bin/python server.py
```

### Windows/Linux + NVIDIA GPU

먼저 [PyTorch 설치 선택기](https://pytorch.org/get-started/locally/)에서 GPU와 CUDA 버전에 맞는 PyTorch 명령을 실행합니다. 이어서 다음 명령을 사용합니다.

```powershell
py -m venv .venv-ai
.venv-ai\Scripts\activate
python -m pip install -r requirements-ai-transformers.txt
python scripts\install_model_bundle.py "%USERPROFILE%\Downloads\resonance-qwen3-4b-runtime.zip"
python server.py
```

Linux에서는 같은 PyTorch 설치 후 다음 명령을 사용합니다.

```bash
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-ai-transformers.txt
python scripts/install_model_bundle.py ~/Downloads/resonance-qwen3-4b-runtime.zip
python server.py
```

CUDA가 있으면 4-bit로 로드하고, 없으면 CPU로 실행합니다. CPU 모드는 Qwen3 4B 전체 가중치를 메모리에 올리므로 16GB 이상 RAM을 권장하지만 실사용은 NVIDIA GPU 환경을 권장합니다.

### ZIP을 받을 수 없을 때

운영체제를 자동 감지해 호환되는 기본 모델을 Hugging Face에서 받을 수 있습니다. 학습 어댑터는 저장소의 `local_ai/adapters/`에 포함되어 있으므로, 일반적으로 다시 학습할 필요는 없습니다.

```bash
python scripts/download_local_model.py
```

`RESONANCE_BACKEND=mlx` 또는 `RESONANCE_BACKEND=transformers` 환경 변수로 자동 선택을 덮어쓸 수 있습니다.

## 직접 학습하기

파티·캐릭터 데이터가 크게 바뀌었거나 답변 스타일을 직접 조정할 때만 재학습하면 됩니다. 학습 데이터는 `scripts/build_chat_dataset.py`가 `data/characters.json`과 `data/team_rules.json`을 읽어 `local_ai/dataset/`에 생성합니다. 캐릭터 이름을 답변 코드에 고정하는 방식이 아니라, 서비스 실행 시 추천 엔진이 현재 보유풀·역할·점수·대체 조합을 모델 컨텍스트로 전달합니다.

### Apple Silicon MLX

```bash
.venv-ai/bin/python scripts/download_local_model.py --backend mlx
.venv-ai/bin/python scripts/build_chat_dataset.py
.venv-ai/bin/python scripts/train_chatbot.py
```

완료된 어댑터는 `local_ai/adapters/qwen3-4b-mlx/`에 배포되고, 실행별 로그·손실·평가 보고서는 `local_ai/runs/<실행 시각>/`에 남습니다.

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

현재 컴퓨터에 준비된 기본 모델과 최신 학습 어댑터를 묶습니다.

```bash
python scripts/package_model_bundle.py
```

MLX와 Transformers 기본 모델을 모두 내려받은 뒤 완전한 멀티 플랫폼 오프라인 번들을 만들 수도 있습니다.

```bash
python scripts/download_local_model.py --backend all
python scripts/package_model_bundle.py --runtime universal
```

생성 파일은 `local_ai/dist/resonance-qwen3-4b-runtime.zip`입니다. `universal` ZIP은 MLX와 Transformers 기본 가중치를 모두 포함하므로 크기가 매우 큽니다. 일반 배포는 작은 플랫폼 번들 하나와 설치기의 자동 다운로드 방식을 권장하고, 완전 오프라인 배포가 필요할 때만 범용 ZIP을 사용하세요.

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
