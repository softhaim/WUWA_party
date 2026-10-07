import {initializeApp} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import {getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";
import {collection, doc, getDocs, getFirestore, serverTimestamp, setDoc, writeBatch} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js";
import {getFunctions, httpsCallable} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-functions.js";
import {initializeAppCheck, ReCaptchaEnterpriseProvider, ReCaptchaV3Provider} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app-check.js";
import {getAI, getGenerativeModel, GoogleAIBackend, ThinkingLevel} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-ai.js";
import {recommendInBrowser} from "./cloud-planner.js?v=20261007-core-fallback";

let plannerRequestId=0;

function runPlanner(payload,onProgress){
  if(typeof Worker==="undefined"){
    return new Promise((resolve,reject)=>setTimeout(()=>{
      try{resolve(recommendInBrowser(payload));}catch(error){reject(error);}
    },0));
  }
  return new Promise((resolve,reject)=>{
    const worker=new Worker("./planner-worker.js?v=20261007-core-fallback",{type:"module"});
    const id=++plannerRequestId;
    const stop=()=>worker.terminate();
    worker.onmessage=event=>{
      const message=event.data||{};
      if(message.id!==id)return;
      if(message.type==="progress"){onProgress?.(message.message);return;}
      stop();
      if(message.type==="result")resolve(message.result);
      else reject(new Error(message.message||"파티 구성을 계산하지 못했어요."));
    };
    worker.onerror=event=>{stop();reject(new Error(event.message||"파티 계산 작업을 시작하지 못했어요."));};
    worker.postMessage({id,payload});
  });
}

const authReady = auth => new Promise(resolve => {
  const unsubscribe=onAuthStateChanged(auth,user=>{unsubscribe();resolve(user);});
});

const cleanRosterItem = item => {
  const uses=Number(item.max_uses);
  return {
    character_id:String(item.character_id),
    owned:Boolean(item.owned),
    sequence:Math.trunc(Math.max(0,Math.min(6,Number(item.sequence)||0))),
    level:Math.trunc(Math.max(1,Math.min(90,Number(item.level)||1))),
    build_status:["미육성","육성 중","실전 가능","완성"].includes(item.build_status)?item.build_status:"미육성",
    max_uses:Number.isFinite(uses)?Math.trunc(Math.max(0,Math.min(10,uses))):1,
    signature_weapon:Boolean(item.signature_weapon),
    weapon_rank:Math.trunc(Math.max(1,Math.min(5,Number(item.weapon_rank)||1))),
    updated_at:serverTimestamp()
  };
};

const compactText=(value,max=2000)=>String(value||"").replace(/\s+/g," ").trim().slice(0,max);

function looksIncompleteAnswer(value){
  const text=String(value||"").trim();
  if(!text)return true;
  const boldMarkers=(text.match(/\*\*/g)||[]).length;
  if(boldMarkers%2)return true;
  // Common shapes returned when Gemini reaches its output boundary midway
  // through a heading/list item, even when an SDK does not expose MAX_TOKENS.
  return /(?:[:：]|[-*•]|\d+\.)$/.test(text)||/[([{「『]$/.test(text);
}

function aiErrorText(error){
  const raw=[error?.code,error?.status,error?.message,error?.name].filter(Boolean).join(" ");
  if(/429|resource.?exhausted/i.test(raw)){
    if(/capacity|overloaded/i.test(raw))return "Gemini 모델의 일시적인 처리 용량이 부족해요. 잠시 후 다시 시도해 주세요. (429)";
    return "Gemini API 요청 한도에 도달했어요. 결제 전환 직후라면 유료 할당량 반영에 시간이 걸릴 수 있어요. (429)";
  }
  if(/app.?check|403|permission.?denied/i.test(raw))return "App Check 또는 Gemini API 권한을 확인해 주세요. (403)";
  if(/404|not.?found/i.test(raw))return "설정된 Gemini 모델을 찾지 못했어요. 모델 설정을 확인해 주세요. (404)";
  if(/400|invalid.?argument/i.test(raw))return "Gemini에 전달한 요청 형식을 처리하지 못했어요. (400)";
  return "AI 답변을 생성하지 못했어요. 네트워크 또는 Gemini 서비스 상태를 확인해 주세요.";
}

function plannerFallback(recommendation){
  const teams=recommendation?.configurations?.[0]?.teams||recommendation?.teams||[];
  if(!teams.length)return recommendation?.message||"현재 보유풀에서는 검증된 파티를 구성하기 어려워요.";
  const lines=teams.map((team,index)=>`${index+1}. **${team.members.map(member=>member.name_ko).join(" / ")}** — ${team.score}점\n${team.reason}`);
  return `현재 보유풀과 사용 횟수를 기준으로 검증된 우선 배분은 다음과 같아요.\n\n${lines.join("\n\n")}\n\n캐릭터가 겹칠 때는 한 파티의 단일 최고점보다 완성 가능한 고점 파티 수와 전체 점수 합계를 함께 고려했어요.`;
}

function rosterForQuestion(roster,characters,question,conversationText=question){
  const next=Object.fromEntries(Object.entries(roster||{}).map(([id,state])=>[id,{...state}]));
  const numberWords={한:1,두:2,세:3,네:4};
  const assumptions=[];
  for(const character of [...characters].sort((a,b)=>b.name_ko.length-a.name_ko.length)){
    const shadowed=characters.some(other=>other.name_ko.length>character.name_ko.length&&other.name_ko.includes(character.name_ko)&&question.includes(other.name_ko));
    const escaped=character.name_ko.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
    const occurrences=shadowed?[]:[...conversationText.matchAll(new RegExp(`${escaped}[^,.!?;\\n]{0,24}?(\\d+|한|두|세|네)\\s*번`,"g")),...conversationText.matchAll(new RegExp(`(\\d+|한|두|세|네)\\s*번[^,.!?;\\n]{0,24}?${escaped}`,"g"))];
    const match=occurrences.at(-1);
    if(match&&next[character.id]?.owned){
      const value=numberWords[match[1]]||Number(match[1]);
      if(value>=0&&value<=10){next[character.id].max_uses=value;assumptions.push(`${character.name_ko} 최대 사용 횟수 ${value}회`);}
    }
    const position=shadowed?-1:question.indexOf(character.name_ko);
    if(position<0)continue;
    const nearby=question.slice(Math.max(0,position-20),position+character.name_ko.length+35);
    const hypothetical=/(있다면|있다고\s*가정|보유(?:하고)?\s*있다고|뽑았다면|보유한다면)/.test(nearby);
    if(hypothetical&&!next[character.id]?.owned){
      const previous=next[character.id]||{};
      next[character.id]={character_id:character.id,owned:true,sequence:Number(previous.sequence)||0,level:90,build_status:"실전 가능",max_uses:Number(previous.max_uses)||1,signature_weapon:Boolean(previous.signature_weapon),weapon_rank:Number(previous.weapon_rank)||1};
      assumptions.push(`${character.name_ko}를 S0·Lv.90·실전 가능·1회 사용으로 임시 보유 가정`);
    }
  }
  return {roster:next,assumptions};
}

function groundedAnswer(answer,recommendation,characters,roster,question,additionalApproved=[]){
  const clean=String(answer||"").trim();
  if(!clean)return plannerFallback(recommendation);
  const owned=new Set(Object.entries(roster||{}).filter(([,state])=>state.owned).map(([id])=>id));
  const asked=compactText(question,2000);
  const invalid=characters.filter(character=>!owned.has(character.id)&&!asked.includes(character.name_ko)&&clean.includes(character.name_ko));
  if(invalid.length)return plannerFallback(recommendation);
  const approved=new Set([...(recommendation?.configurations||[]).flatMap(config=>config.teams).map(team=>team.members.map(member=>member.name_ko).sort().join("|")),...additionalApproved]);
  for(const line of clean.split("\n")){
    if((line.match(/\//g)||[]).length!==2)continue;
    const mentioned=characters.filter(character=>line.includes(character.name_ko));
    if(mentioned.length===3&&!approved.has(mentioned.map(character=>character.name_ko).sort().join("|")))return plannerFallback(recommendation);
  }
  return clean;
}

export async function createCloudRuntime(config){
  const app=initializeApp(config);
  const auth=getAuth(app);
  const db=getFirestore(app);
  const functions=getFunctions(app,config.functionsRegion||"asia-northeast3");
  const runtime={user:await authReady(auth),characters:null,rules:null};
  const warmPromises=new Map();
  let manifestPromise=null;
  let aiModel=null;
  let aiFallbackModel=null;
  let aiInitError=null;

  if(config.aiEnabled!==false&&config.appCheckSiteKey){
    try{
      if(["localhost","127.0.0.1"].includes(location.hostname))self.FIREBASE_APPCHECK_DEBUG_TOKEN=true;
      const Provider=config.appCheckProvider==="v3"?ReCaptchaV3Provider:ReCaptchaEnterpriseProvider;
      initializeAppCheck(app,{provider:new Provider(config.appCheckSiteKey),isTokenAutoRefreshEnabled:true});
      const ai=getAI(app,{backend:new GoogleAIBackend()});
      // Gemini 3.6+ rejects custom sampling parameters and upcoming models no
      // longer remap thinkingBudget. Keep only the supported thinking level
      // plus the response-length guard used by the chat UI.
      const generationConfig={
        thinkingConfig:{thinkingLevel:ThinkingLevel.MEDIUM},
        maxOutputTokens:2600
      };
      aiModel=getGenerativeModel(ai,{
        model:config.aiModel||"gemini-3.8-flash",
        generationConfig
      });
      if(config.aiFallbackModel!==false){
        aiFallbackModel=getGenerativeModel(ai,{
          model:config.aiFallbackModel||"gemini-3.1-flash-lite",
          generationConfig
        });
      }
    }catch(error){
      aiInitError=error;
      console.error("Firebase AI Logic initialization failed",error);
    }
  }

  runtime.onAuthChanged=callback=>onAuthStateChanged(auth,callback);
  runtime.signIn=()=>signInWithPopup(auth,new GoogleAuthProvider());
  runtime.signOut=()=>firebaseSignOut(auth);
  runtime.loadCharacters=async()=>{
    const response=await fetch("./data/characters.json",{cache:"no-cache"});
    if(!response.ok)throw new Error("캐릭터 데이터를 불러오지 못했습니다.");
    const order=new Map(["응결","용융","전도","기류","회절","인멸"].map((value,index)=>[value,index]));
    runtime.characters=(await response.json()).sort((a,b)=>(order.get(a.element_ko)??99)-(order.get(b.element_ko)??99)||a.name_ko.localeCompare(b.name_ko,"ko"));
    // Nanoka can publish a new Spine model after the character catalog. Probe
    // only currently unavailable entries so a later upload becomes usable on
    // the already deployed site; the next asset build will cache it locally.
    Promise.all(runtime.characters.filter(item=>item.live2d_available===false&&item.live2d_skeleton_url&&item.live2d_atlas_url).map(async item=>{
      try{
        const [skeleton,atlas]=await Promise.all([
          fetch(item.live2d_skeleton_url,{method:"HEAD",cache:"no-store"}),
          fetch(item.live2d_atlas_url,{method:"HEAD",cache:"no-store"})
        ]);
        if(skeleton.ok&&atlas.ok){item.live2d_available=true;item.live2d_check="runtime-published";}
      }catch(_){/* The 2D fallback remains authoritative until publication. */}
    })).catch(()=>{});
    return runtime.characters;
  };
  runtime.loadRules=async()=>{
    if(runtime.rules)return runtime.rules;
    const response=await fetch("./data/team_rules.json",{cache:"no-cache"});
    if(!response.ok)throw new Error("파티 추천 규칙을 불러오지 못했습니다.");
    runtime.rules=await response.json();
    return runtime.rules;
  };
  runtime.loadRoster=async()=>{
    if(!runtime.user)return {};
    const snapshot=await getDocs(collection(db,"users",runtime.user.uid,"roster"));
    const roster={};
    snapshot.forEach(entry=>{roster[entry.id]={...entry.data(),character_id:entry.id};});
    return roster;
  };
  runtime.saveRoster=async items=>{
    if(!runtime.user)throw new Error("로그인이 필요합니다.");
    const batch=writeBatch(db);
    for(const item of items){
      const clean=cleanRosterItem(item);
      batch.set(doc(db,"users",runtime.user.uid,"roster",clean.character_id),clean,{merge:true});
    }
    batch.set(doc(db,"users",runtime.user.uid),{
      display_name:runtime.user.displayName||"",
      email:runtime.user.email||"",
      updated_at:serverTimestamp()
    },{merge:true});
    await batch.commit();
    return {ok:true,saved:items.length,saved_at:new Date().toISOString(),storage:"Cloud Firestore"};
  };
  runtime.recommend=async(payload,onProgress)=>{
    if(!runtime.user)throw new Error("로그인이 필요합니다.");
    const [characters,rules,roster]=await Promise.all([
      runtime.characters||runtime.loadCharacters(),
      runtime.loadRules(),
      runtime.loadRoster()
    ]);
    if(config.useCloudFunctions===true){
      const call=httpsCallable(functions,"recommend_teams",{timeout:120000});
      const response=await call(payload);
      return response.data;
    }
    return runPlanner({...payload,characters,rules,roster},onProgress);
  };
  runtime.aiStatus=()=>{
    if(config.aiEnabled===false)return {ready:false,bundle_required:false,setup_title:"AI 가이드가 비활성화되어 있어요",message:"사이트 관리자가 Firebase AI Logic을 활성화해야 해요."};
    if(!config.appCheckSiteKey)return {ready:false,bundle_required:false,setup_title:"AI 연결 설정이 필요해요",message:"App Check 사이트 키를 cloud-env.js에 등록한 뒤 다시 배포해 주세요."};
    if(aiInitError||!aiModel)return {ready:false,bundle_required:false,setup_title:"AI 연결을 시작하지 못했어요",message:"Firebase AI Logic과 App Check 설정을 확인해 주세요."};
    if(!runtime.user)return {ready:false,bundle_required:false,setup_title:"로그인이 필요해요",message:"Google로 로그인하면 저장된 보유풀을 바탕으로 AI 가이드를 이용할 수 있어요."};
    return {ready:true,bundle_required:false,provider:"Firebase AI Logic",model:config.aiModel||"gemini-3.8-flash"};
  };
  runtime.chat=async payload=>{
    const status=runtime.aiStatus();
    if(!status.ready)throw new Error(status.message);
    const [characters,rules,roster]=await Promise.all([
      runtime.characters||runtime.loadCharacters(),
      runtime.loadRules(),
      runtime.loadRoster()
    ]);
    const history=(payload.messages||[]).slice(-10).map(message=>({role:message.role==="assistant"?"assistant":"user",content:compactText(message.content)}));
    const question=history.filter(message=>message.role==="user").at(-1)?.content||"현재 추천을 설명해 주세요.";
    const conversationText=history.filter(message=>message.role==="user").slice(-4).map(message=>message.content).join("\n");
    const scenario=rosterForQuestion(roster,characters,question,conversationText);
    const planningRoster=scenario.roster;
    const recommendation=await runPlanner({characters,rules,roster:planningRoster,team_count:payload.team_count||3});
    const owned=characters.filter(character=>planningRoster[character.id]?.owned).map(character=>{
      const state=planningRoster[character.id];
      return {name:character.name_ko,role:character.role,element:character.element_ko,level:state.level,sequence:state.sequence,build:state.build_status,max_uses:state.max_uses,signature_weapon:state.signature_weapon,weapon_rank:state.weapon_rank};
    });
    const configurations=(recommendation.configurations||[]).slice(0,3).map(config=>({
      label:config.label,total_score:config.total_score,
      teams:config.teams.map(team=>({members:team.members.map(member=>({name:member.name_ko,slot:member.slot})),score:team.score,readiness:team.readiness,reason:team.reason,tags:team.tags}))
    }));
    const characterById=new Map(characters.map(character=>[character.id,character]));
    const mentionedIds=new Set(characters.filter(character=>conversationText.includes(character.name_ko)&&!characters.some(other=>other.name_ko.length>character.name_ko.length&&other.name_ko.includes(character.name_ko)&&conversationText.includes(other.name_ko))).map(character=>character.id));
    const relevantTemplates=(rules.templates||[]).filter(template=>template.members.some(id=>mentionedIds.has(id))).sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,30).map(template=>({
      members:template.members.map(id=>characterById.get(id)?.name_ko||id),score:template.score,tier:template.tier,status:template.status,patch:template.patch,label:template.label,tags:template.tags
    }));
    const templateKeys=relevantTemplates.map(template=>[...template.members].sort().join("|"));
    const prompt=`당신은 명조 파티 플래너의 한국어 AI 가이드예요. 항상 친근한 존댓말(~해요, ~예요)을 사용하세요.

규칙:
- 사용자의 마지막 질문에 먼저 직접 답하고, 묻지 않은 전체 파티 목록을 습관적으로 나열하지 마세요.
- 아래 앱 데이터만 사실로 사용하세요. 캐릭터 역할, 버프, 효과, 점수, 조합을 지어내지 마세요.
- 내 보유풀 질문에는 보유하지 않은 캐릭터를 추천하지 마세요. 단, 사용자가 보유를 가정한 캐릭터는 아래 시나리오 가정에 따라 임시 보유로 취급하세요.
- 파티를 제안할 때는 반드시 아래 검증된 추천 구성 또는 관련 검증 템플릿에 존재하는 3인 조합만 사용하세요.
- 캐릭터 사용 횟수와 중복 제한은 검증된 추천 구성에 이미 반영되어 있어요.
- 현재 최적 구성에 캐릭터가 보이지 않는다는 이유만으로 검증 조합이 없다고 결론 내리지 마세요. 관련 검증 템플릿을 확인하고, 핵심 파츠가 다른 파티와 충돌하면 그 자원 충돌을 정확히 설명하세요.
- 가정 질문에서는 시나리오를 적용해 다시 계산된 추천 구성과 기존 보유풀의 차이를 설명하세요.
- 사용자가 '히유키에는 수수를 쓴다'처럼 특정 배치를 명시하면 그 배치를 고정 조건으로 존중하세요. 전역 최적 구성이 그 조건과 다르면, 사용자의 조건을 지킨 답과 전역 최적안을 구분해서 설명하세요.
- 관련 검증 템플릿의 score는 조합 자체의 기준점이고, 현재 로스터의 실제 점수는 검증된 추천 구성의 score예요. 두 점수를 혼동하지 마세요.
- 정보가 부족하면 추측하지 말고 부족한 정보를 짧게 밝혀 주세요.
- 중요한 결론은 **굵게**, 목록은 '- ' 또는 '1. ' 형식으로 읽기 쉽게 작성하세요.
- 답변은 보통 400~700자, 최대 8개 항목 안에서 간결하게 작성하고 선택 이유와 대체 배분의 손익을 설명하세요.
- 중간 제목이나 목록을 시작했다면 반드시 내용을 채우고, 마지막 문장까지 완결해서 끝내세요.

메타 데이터: ${JSON.stringify({patch:rules.meta_patch,updated_at:rules.meta_updated_at,rules_version:rules.version})}
보유 캐릭터: ${JSON.stringify(owned)}
시나리오 가정: ${JSON.stringify(scenario.assumptions)}
검증된 추천 구성: ${JSON.stringify(configurations)}
질문 관련 검증 템플릿: ${JSON.stringify(relevantTemplates)}
최근 대화: ${JSON.stringify(history)}

마지막 질문: ${question}`;
    try{
      let result,usedModel=config.aiModel||"gemini-3.8-flash",usedGenerator=aiModel;
      try{
        result=await aiModel.generateContent(prompt);
      }catch(primaryError){
        const retryable=/429|resource.?exhausted|capacity|overloaded/i.test([primaryError?.code,primaryError?.status,primaryError?.message].filter(Boolean).join(" "));
        if(!retryable||!aiFallbackModel)throw primaryError;
        console.warn("Primary Gemini model unavailable; retrying with fallback",{model:usedModel,code:primaryError?.code,status:primaryError?.status});
        usedModel=config.aiFallbackModel||"gemini-3.1-flash-lite";
        usedGenerator=aiFallbackModel;
        result=await usedGenerator.generateContent(prompt);
      }
      const finishReason=String(result.response.candidates?.[0]?.finishReason||"");
      if(/MAX_TOKENS|LENGTH/i.test(finishReason)||looksIncompleteAnswer(result.response.text())){
        const repairPrompt=`${prompt}\n\n직전 답변이 길이 제한으로 중간에 끊겼어요. 같은 근거만 사용해 핵심 결론, 이유, 대체안의 손익을 650자 이내의 완결된 한국어 답변으로 처음부터 다시 작성하세요.`;
        result=await usedGenerator.generateContent(repairPrompt);
      }
      const generated=result.response.text();
      const answer=looksIncompleteAnswer(generated)?plannerFallback(recommendation):groundedAnswer(generated,recommendation,characters,planningRoster,question,templateKeys);
      return {answer,sources:["내 보유풀","검증된 파티 플래너",`Gemini ${usedModel}`],grounded:true};
    }catch(error){
      console.error("Firebase AI Logic request failed",{code:error?.code,status:error?.status,message:error?.message,name:error?.name});
      throw new Error(aiErrorText(error));
    }
  };
  const warmAsset=async url=>{
    if(warmPromises.has(url))return warmPromises.get(url);
    const promise=(async()=>{
      const cache=typeof caches!=="undefined"?await caches.open("resonance-live2d-v2"):null;
      if(cache&&await cache.match(url))return {url,cached:true};
      const response=await fetch(url,{cache:"force-cache"});
      if(!response.ok)throw new Error(`Live2D 파일 ${response.status}`);
      if(cache)await cache.put(url,response.clone());
      await response.arrayBuffer();
      return {url,cached:false};
    })().catch(error=>{warmPromises.delete(url);throw error;});
    warmPromises.set(url,promise);
    return promise;
  };
  runtime.preloadLive2d=async(characterIds=[],includeRemaining=false,onProgress)=>{
    manifestPromise ||= fetch("./data/live2d-manifest.json",{cache:"force-cache"}).then(response=>response.ok?response.json():{characters:{},all:[]});
    const manifest=await manifestPromise;
    const priority=[...new Set(characterIds.flatMap(id=>manifest.characters?.[id]||[]))];
    const remaining=includeRemaining?(manifest.all||[]):[];
    const queue=[...new Set([...priority,...remaining])].filter(Boolean);
    const total=queue.length;
    let completed=0;
    const report=(url,cached,error)=>onProgress?.({completed,total,percent:total?Math.round(completed/total*100):100,url,cached,error});
    report("",true);
    const download=async()=>{while(queue.length){const url=queue.shift();try{const result=await warmAsset(url);completed++;report(url,result.cached);}catch(error){completed++;report(url,false,error.message);console.debug("Live2D preload skipped",url,error);}}};
    await Promise.all(Array.from({length:Math.min(includeRemaining?2:3,queue.length)},download));
    return {completed,total,percent:100};
  };
  return runtime;
}
