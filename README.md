# Resonance Lab

명조: 워더링 웨이브의 보유 캐릭터와 육성 상태를 기록하고, 현재 보유풀에서 만들 수 있는 파티를 추천받는 웹 앱입니다.

## 화면 미리보기

### 캐릭터 관리

<img width="1539" height="983" alt="Resonance Lab 캐릭터 관리 화면" src="https://github.com/user-attachments/assets/d35a3fb8-6891-4b36-a050-c14363ef6222" />

### 파티 추천

<img width="1539" height="983" alt="Resonance Lab 파티 추천 화면" src="https://github.com/user-attachments/assets/601039e9-91cc-4281-a49f-06bd55b0377a" />

### AI 가이드

<img width="1617" height="979" alt="Resonance Lab 로컬 AI 가이드 화면" src="https://github.com/user-attachments/assets/f6081a7b-fb7f-4475-aa4f-fe2f8ecfe411" />

## 바로 사용하기

설치 없이 이용하려면 아래 공개 웹에 접속하세요.

### [Resonance Lab 웹 서비스 열기](https://wuwa-335e0.web.app)

1. 오른쪽 위의 **Google로 로그인**을 누릅니다.
2. 캐릭터 카드를 눌러 보유 여부와 육성 상태를 입력합니다.
3. **저장하기**를 누르면 현재 Google 계정에 설정이 저장됩니다.
4. 위 메뉴에서 **파티 플래너**로 이동합니다.
5. 필요한 파티 수를 선택하고 **자동 파티 구성**을 누릅니다.
6. 추천 구성 A·B·C를 비교해 캐릭터 배분이 가장 알맞은 구성을 선택합니다.
7. **AI 가이드**에서 현재 보유풀의 파티 배분이나 육성 순서를 질문할 수 있습니다.

저장한 로스터는 같은 Google 계정으로 로그인하면 다른 기기에서도 이어서 사용할 수 있습니다.

## 웹 AI 가이드 사용법

공개 웹의 **AI 가이드**는 Firebase AI Logic과 Gemini를 사용합니다. 모델 파일이나 Python을 설치할 필요 없이 Google 로그인만 하면 사용할 수 있습니다.

1. [Resonance Lab 웹 서비스](https://wuwa-335e0.web.app)에 Google 계정으로 로그인합니다.
2. **캐릭터** 화면에서 보유 캐릭터, 돌파, 레벨, 육성 상태와 최대 사용 횟수를 입력하고 저장합니다.
3. **파티 플래너**에서 원하는 파티 수를 선택하고 **자동 파티 구성**을 실행합니다.
4. **AI 가이드**로 이동해 추천 결과에서 궁금한 점을 질문합니다.

AI는 로그인한 계정에 저장된 로스터, 현재 선택한 파티 수, 검증된 파티 조합과 최근 대화를 함께 참고합니다. 따라서 아래처럼 조건을 구체적으로 적을수록 더 알맞은 답을 받을 수 있습니다.

- `치사를 2번 사용할 수 있을 때 내 보유풀에서는 어디에 배분하는 게 좋아?`
- `히유키 파티에는 수수를 고정하고, 남은 치사를 다른 파티에 배분해 줘.`
- `현재 추천 구성 A와 B의 차이와 캐릭터 배분 손익을 설명해 줘.`
- `내 미육성 캐릭터 중 다음으로 누구를 키우면 파티가 가장 강해져?`
- `양양:현령을 보유했다고 가정하면 현재 추천이 어떻게 바뀌어?`

대화 중에 제시한 사용 횟수나 가정 조건은 해당 질문을 분석할 때 반영됩니다. 실제 로스터를 영구적으로 바꾸려면 **캐릭터** 화면에서 값을 수정하고 다시 저장해야 합니다. 파티 데이터에 등록되지 않은 신규 조합이나 아직 검증되지 않은 정보는 AI가 임의로 만들어 내지 않고, 확인 가능한 범위 안에서 답하도록 구성되어 있습니다.

AI 응답이 일시적으로 생성되지 않으면 잠시 뒤 다시 시도해 주세요. 로그인 상태와 로스터 저장 여부도 함께 확인할 수 있습니다. 웹 AI 대신 모델과 대화를 내 컴퓨터에서 직접 실행하고 싶다면 아래의 [로컬 앱과 로컬 AI 사용하기](#로컬-앱과-로컬-ai-사용하기)를 이용하세요.

## 캐릭터 설정 방법

캐릭터 카드를 누르면 다음 항목을 설정할 수 있습니다.

- 보유 여부
- 공명 체인 S0~S6
- 레벨과 `MAX 90`
- 육성 상태: 미육성, 육성 중, 실전 가능, 완성
- 최대 사용 횟수
- 전용 무기 보유 여부와 재련 단계

레벨, 육성 상태, 사용 횟수 같은 육성 정보를 변경하면 보유 상태도 자동으로 켜집니다. 방랑자의 속성별 형태는 하나의 캐릭터로 취급하므로 한 형태를 파티에 사용하면 다른 형태의 사용 횟수도 함께 차감됩니다.

캐릭터 상세 화면은 Live2D를 기본으로 표시합니다. 처음 접속하면 Live2D 파일을 브라우저 캐시에 준비하며, 이후 방문과 캐릭터 전환은 더 빠르게 동작합니다. 처음 이용할 때는 네트워크 환경에 따라 잠시 로딩될 수 있습니다.

## 파티 추천 기준

파티 플래너는 다음 정보를 함께 계산합니다.

- 현재 보유한 캐릭터
- 캐릭터별 최대 사용 횟수
- 검증된 최신 메타 조합과 대체 조합
- 캐릭터의 역할과 버프 호환성
- 공명 체인, 전용 무기와 재련
- 레벨과 육성 완성도
- 한 파티의 최고점뿐 아니라 전체 파티 배분 후의 성능

서로 겹치는 핵심 캐릭터가 있으면 한 파티만 강하게 만드는 대신, 완성 가능한 고점 파티의 수와 전체 점수를 비교합니다. 억지로 맞지 않는 조합을 채우기보다 실제로 사용할 수 있는 조합을 우선합니다.


## 웹 버전과 로컬 버전

| 버전 | 추천 대상 | 데이터 저장 | AI 가이드 |
|---|---|---|---|
| [공개 웹](https://wuwa-335e0.web.app) | 설치 없이 바로 사용하려는 사용자 | 로그인한 Firebase 계정 | Firebase AI Logic + Gemini, 모델 다운로드 불필요 |
| 로컬 앱 | 내 PC에서 파티 플래너를 실행하려는 사용자 | 내 컴퓨터의 `roster.db` | AI 없이도 파티 추천 사용 가능 |
| 로컬 앱 + 로컬 AI | 모델과 대화를 내 PC에서 실행하려는 사용자 | 내 컴퓨터의 `roster.db` | Apple Silicon은 MLX, NVIDIA GPU는 CUDA |

공개 웹에서 입력한 로스터와 로컬 버전의 `roster.db`는 자동으로 동기화되지 않습니다.

## 로컬 앱과 로컬 AI 사용하기

로컬 앱은 공개 웹과 별개의 선택 사항입니다. 공개 웹의 AI 가이드를 이용할 때는 이 절차를 진행하거나 모델 ZIP을 받을 필요가 없습니다.

### AI 없이 로컬 파티 플래너 실행

로컬 파티 플래너만 사용한다면 Python 3.11 이상 외에 추가 패키지가 필요하지 않습니다.

```bash
git clone https://github.com/softhaim/WUWA_party.git
cd WUWA_party
python3 server.py
```

Windows에서는 마지막 명령을 `py server.py`로 실행할 수 있습니다. 서버가 시작되면 [http://127.0.0.1:8000](http://127.0.0.1:8000)을 여세요.

처음 실행할 때 Live2D 파일을 `.cache/live2d-assets/`에 준비하므로 서버가 열리기까지 시간이 걸릴 수 있습니다. 준비가 끝난 뒤에는 로컬 캐시를 사용합니다.

### 로컬 AI 추가 설치

AI 육성 가이드는 보유 캐릭터와 파티 플래너 결과를 바탕으로 파티 배분, 대체 캐릭터와 육성 방향에 답합니다. Apple Silicon Mac은 MLX를 사용하고, Windows·Linux의 NVIDIA GPU는 CUDA용 Transformers를 사용합니다.

#### 1. 모델 번들 받기

[Resonance AI 모델 번들 다운로드](https://drive.google.com/drive/folders/1TcNuDnVOnchhMmfK9phJ_TMabgfWhUC8?usp=sharing)

다운로드한 `resonance-qwen3-4b-runtime.zip`을 압축 해제하지 말고 아래 위치에 넣습니다.

```text
WUWA_party/local_ai/bundles/resonance-qwen3-4b-runtime.zip
```

기본 폴더에 넣으면 설치 명령에서 ZIP 경로는 쓰지 않아도 됩니다. 다른 폴더에 보관하려면 설치 명령 뒤에 ZIP의 전체 경로를 지정할 수도 있습니다.

이 번들은 Mac용 MLX 모델과 Windows·Linux용 Transformers 모델, 두 형식의 학습 어댑터를 함께 포함합니다. 운영체제와 관계없이 같은 Universal ZIP을 사용할 수 있습니다.

#### 2-A. Apple Silicon Mac

```bash
python3 -m venv .venv-ai
.venv-ai/bin/python -m pip install -r requirements-ai-mlx.txt
.venv-ai/bin/python scripts/install_model_bundle.py
.venv-ai/bin/python server.py
```

#### 2-B. Windows + NVIDIA GPU

먼저 [PyTorch 설치 선택기](https://pytorch.org/get-started/locally/)에서 Windows와 자신의 CUDA 환경에 맞는 PyTorch 설치 명령을 실행하세요. CPU용 PyTorch가 설치되어 있으면 모델이 GPU가 아닌 RAM을 사용하므로 반드시 `torch.cuda.is_available()`이 `True`인지 확인해야 합니다.

```powershell
py -m venv .venv-ai
.venv-ai\Scripts\activate
python -m pip install -r requirements-ai-transformers.txt
python scripts\install_model_bundle.py
python scripts\check_ai_runtime.py
python server.py
```

정상적인 CUDA 환경에서는 진단 결과에 다음 항목이 표시됩니다.

```text
"cuda_available": true
"gpu_name": "NVIDIA ..."
[ok] CUDA 4-bit 추론 준비가 확인됐어요.
```

PowerShell에서 가상환경 활성화가 차단되면 현재 터미널에만 다음 정책을 적용한 뒤 다시 실행하세요.

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

#### 2-C. Linux + NVIDIA GPU

PyTorch 설치 선택기에서 CUDA용 PyTorch를 설치한 뒤 다음 명령을 실행합니다.

```bash
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-ai-transformers.txt
python scripts/install_model_bundle.py
python scripts/check_ai_runtime.py
python server.py
```

#### 설치 후 파일 위치

설치 프로그램은 번들의 파일을 자동으로 다음 위치에 배치합니다.

- 기본 모델: `local_ai/models/`
- 학습된 LoRA 어댑터: `local_ai/adapters/`

설치 완료 후 원본 ZIP은 더 이상 실행에 사용되지 않으므로 삭제하거나 다른 곳으로 옮겨도 됩니다. 앱은 설치된 모델과 어댑터를 읽습니다.

가상환경 이름은 `.venv-ai`로 고정되어 있지 않습니다. 원하는 이름의 환경에 패키지를 설치했다면 그 환경의 Python으로 설치 프로그램과 `server.py`를 실행하면 됩니다.

#### 모델 번들을 받을 수 없을 때

기본 모델을 Hugging Face에서 직접 받을 수 있습니다.

```bash
python scripts/download_local_model.py
```

다운로드한 모델만으로도 실행할 수 있으며, 저장소의 `local_ai/adapters/`에 호환되는 학습 어댑터가 있으면 자동으로 적용됩니다.

#### Windows에서 GPU를 사용하지 않을 때

다음 명령으로 현재 Python 환경의 PyTorch를 확인하세요.

```powershell
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

CUDA 버전이 `None`이거나 마지막 값이 `False`라면 CPU용 PyTorch가 설치된 상태입니다. 기존 PyTorch를 제거한 뒤 설치 선택기에서 안내하는 CUDA용 명령으로 다시 설치하세요.

```powershell
pip uninstall torch torchvision torchaudio -y
```

기본 설정은 CUDA를 찾지 못했을 때 RAM으로 조용히 전환하지 않고 원인을 표시합니다. CPU 실행이 꼭 필요한 경우에만 `RESONANCE_ALLOW_CPU=1`을 지정할 수 있지만, 생성 속도가 매우 느릴 수 있습니다.

## 데이터 저장과 개인정보

- 공개 웹 로스터는 로그인한 Firebase 사용자 UID 아래에 저장됩니다.
- 다른 사용자는 Firestore 보안 규칙에 따라 해당 로스터를 읽거나 수정할 수 없습니다.
- 공개 웹에서 AI 가이드에 질문하면 저장된 보유풀, 파티 플래너 데이터, 질문과 최근 대화가 답변 생성을 위해 Firebase AI Logic의 Gemini에 전달됩니다.
- 로컬 버전의 로스터는 프로젝트 폴더의 `roster.db`에만 저장됩니다.
- 로컬 AI 대화와 추론은 사용자의 컴퓨터에서 처리됩니다.
- 모델 가중치, 모델 ZIP, 로컬 DB, 실행 로그와 캐시 파일은 Git 저장소에 포함되지 않습니다.

## 개발 및 학습

파티·캐릭터 데이터가 크게 변경되었거나 답변 스타일을 직접 조정하려는 경우에만 모델을 다시 학습하면 됩니다. 자세한 학습 구조와 파일 형식은 [local_ai/README.md](local_ai/README.md)를 참고하세요.

### Apple Silicon MLX 학습

```bash
.venv-ai/bin/python scripts/download_local_model.py --backend mlx
.venv-ai/bin/python scripts/build_chat_dataset.py
.venv-ai/bin/python scripts/train_chatbot.py
```

### Windows·Linux CUDA 학습

```powershell
python -m pip install -r requirements-ai-cuda.txt
python scripts\build_chat_dataset.py
python scripts\train_chatbot_cuda.py
```

학습 결과는 `local_ai/adapters/`에 저장되며, 실행 로그와 평가 보고서는 `local_ai/runs/<실행 시각>/`에서 확인할 수 있습니다.

### 저장소에서 공개 웹 복원하기

이 저장소에는 애플리케이션 코드와 복구에 필요한 예시 설정만 포함됩니다. 실제 Firebase 웹 설정은 Git에 저장하지 않습니다.

1. 저장소를 복제합니다.
2. `cloud/cloud-env.example.js`를 `cloud/cloud-env.js`로 복사합니다.
3. [Firebase Console](https://console.firebase.google.com/)에서 프로젝트 설정 → 일반 → 내 앱 → SDK 설정 및 구성으로 이동합니다.
4. 웹 앱의 Firebase 설정값을 `cloud/cloud-env.js`에 입력합니다.
5. Firebase Authentication에서 Google 로그인을 활성화하고 Firestore Database를 생성합니다.
6. Firebase Console의 **Firebase AI Logic**에서 Gemini Developer API를 연결합니다.
7. Firebase Console의 **App Check**에서 웹 앱을 reCAPTCHA Enterprise로 등록하고, 발급된 사이트 키를 `appCheckSiteKey`에 입력합니다.
8. `aiEnabled`는 `true`, `appCheckProvider`는 `"enterprise"`, `aiModel`은 `"gemini-3.8-flash"`로 둡니다.
9. Firebase CLI 로그인 후 공개 웹과 보안 규칙을 배포합니다.

```bash
firebase login
firebase deploy --only hosting,firestore
```

로컬 주소에서 공개 웹 빌드를 시험하면 브라우저 콘솔에 App Check 디버그 토큰이 표시됩니다. Firebase Console → App Check → 디버그 토큰에 한 번 등록하면 로컬 테스트 요청도 허용됩니다. 운영 배포에서는 디버그 토큰을 코드나 Git에 저장하지 않습니다.

`cloud/cloud-env.js`는 `.gitignore`에 포함되어 있으므로 실제 설정값이 다시 커밋되지 않습니다. Firebase 웹 API 키는 Firebase 프로젝트 식별에 사용되지만, Google Cloud Console의 API 및 서비스 → 사용자 인증 정보에서 다음 제한을 확인하세요.

- 애플리케이션 제한: 운영 도메인과 필요한 로컬 개발 주소만 허용
- API 제한: Firebase에서 사용하는 API만 허용
- Firebase 외 유료 Google API는 별도 키로 분리

실제 키가 Git 기록이나 외부 문서에 들어갔다면 해당 값을 다시 사용하지 마세요. Google Cloud Console의 사용자 인증 정보에서 키를 교체한 뒤 새 값을 로컬 `cloud/cloud-env.js`에만 입력하고 Hosting을 다시 배포하세요. 새 설정으로 로그인과 로스터 저장을 확인한 다음 이전 키를 삭제하면 됩니다.

모델 가중치는 Git에 포함되지 않으므로 로컬 AI까지 복원하려면 [모델 번들](https://drive.google.com/drive/folders/1TcNuDnVOnchhMmfK9phJ_TMabgfWhUC8?usp=sharing)을 다시 설치해야 합니다.

### 테스트

```bash
python3 -m unittest discover -s tests -v
```

## 데이터와 라이선스

캐릭터 이미지와 Live2D 경로는 Nanoka의 공개 정적 데이터를 기반으로 사용합니다. 파티 추천은 `data/team_rules.json`의 메타 조합과 사용자가 입력한 보유·육성 정보를 함께 계산합니다.

로컬 AI의 기본 언어 모델은 Apache-2.0 라이선스의 [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)과 [MLX 4-bit 변환본](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit)를 사용합니다.
