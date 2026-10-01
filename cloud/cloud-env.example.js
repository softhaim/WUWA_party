// Firebase Console > 프로젝트 설정 > 일반 > 내 앱 > SDK 설정 및 구성에서
// 자신의 웹 앱 설정을 복사한 뒤 이 파일을 cloud-env.js로 저장하세요.
// cloud-env.js는 Git에서 제외되며 실제 배포 환경에서만 사용합니다.
window.RESONANCE_CLOUD_CONFIG = {
  apiKey: "YOUR_FIREBASE_WEB_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.firebasestorage.app",
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
  appId: "YOUR_FIREBASE_APP_ID",
  functionsRegion: "asia-northeast3",
  useCloudFunctions: false,
  // Firebase Console > App Check > 웹 앱에 등록한 reCAPTCHA Enterprise 사이트 키입니다.
  // 사이트 키는 브라우저에 공개되는 식별자이며 비밀 키가 아닙니다.
  appCheckSiteKey: "YOUR_RECAPTCHA_ENTERPRISE_SITE_KEY",
  appCheckProvider: "enterprise",
  aiEnabled: true,
  aiModel: "gemini-3.8-flash",
  aiFallbackModel: "gemini-3.1-flash-lite"
};
