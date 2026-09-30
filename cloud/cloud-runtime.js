import {initializeApp} from "https://www.gstatic.com/firebasejs/12.3.0/firebase-app.js";
import {getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, signOut as firebaseSignOut} from "https://www.gstatic.com/firebasejs/12.3.0/firebase-auth.js";
import {collection, doc, getDocs, getFirestore, serverTimestamp, setDoc, writeBatch} from "https://www.gstatic.com/firebasejs/12.3.0/firebase-firestore.js";
import {getFunctions, httpsCallable} from "https://www.gstatic.com/firebasejs/12.3.0/firebase-functions.js";
import {recommendInBrowser} from "./cloud-planner.js";

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

export async function createCloudRuntime(config){
  const app=initializeApp(config);
  const auth=getAuth(app);
  const db=getFirestore(app);
  const functions=getFunctions(app,config.functionsRegion||"asia-northeast3");
  const runtime={user:await authReady(auth),characters:null,rules:null};
  const warmed=new Set();
  let manifestPromise=null;

  runtime.onAuthChanged=callback=>onAuthStateChanged(auth,callback);
  runtime.signIn=()=>signInWithPopup(auth,new GoogleAuthProvider());
  runtime.signOut=()=>firebaseSignOut(auth);
  runtime.loadCharacters=async()=>{
    const response=await fetch("./data/characters.json",{cache:"no-cache"});
    if(!response.ok)throw new Error("캐릭터 데이터를 불러오지 못했습니다.");
    runtime.characters=await response.json();
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
  runtime.recommend=async payload=>{
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
    return recommendInBrowser({...payload,characters,rules,roster});
  };
  runtime.preloadLive2d=async(characterIds=[],includeRemaining=true)=>{
    manifestPromise ||= fetch("./data/live2d-manifest.json",{cache:"force-cache"}).then(response=>response.ok?response.json():{characters:{},all:[]});
    const manifest=await manifestPromise;
    const priority=[...new Set(characterIds.flatMap(id=>manifest.characters?.[id]||[]))];
    const remaining=includeRemaining?(manifest.all||[]):[];
    const queue=[...priority,...remaining].filter(url=>url&&!warmed.has(url));
    queue.forEach(url=>warmed.add(url));
    const worker=async()=>{while(queue.length){const url=queue.shift();try{const response=await fetch(url,{cache:"force-cache"});if(response.ok)await response.arrayBuffer();}catch(error){warmed.delete(url);console.debug("Live2D preload skipped",url,error);}}};
    await Promise.all(Array.from({length:Math.min(4,queue.length)},worker));
  };
  return runtime;
}
