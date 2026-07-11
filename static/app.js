const state = { characters: [], roster: {}, filterElement: "", filterWeapon: "", filterRarity: "", filterRole: "", activeId: null, spineApp: null, spineLoading: null, nanokaSpineComponent: null, nanokaSpineModule: null, live2dRunId: 0 };
const COLORS = {응결:"#173849",용융:"#4c2520",전도:"#312548",기류:"#193d36",회절:"#4a4120",인멸:"#3d2545"};
const ELEMENTS = ["응결","용융","전도","기류","회절","인멸"];
const WEAPONS = ["대검","직검","권총","권갑","증폭기"];
const ROLES = ["딜러","서브딜러","서포터"];
const $ = (selector) => document.querySelector(selector);
const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
const imageUrl = (value) => value?.startsWith("/") ? `${API_BASE}${value}` : value;
const SPINE_SCRIPTS = [
  "https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js",
  "https://cdn.jsdelivr.net/npm/pixi-spine@4.0.4/dist/pixi-spine.umd.js"
];

async function api(path, options={}) {
  let response;
  try { response = await fetch(`${API_BASE}${path}`, {headers:{"Content-Type":"application/json"}, ...options}); }
  catch (_) { throw new Error("로컬 서버에 연결할 수 없습니다. python3 server.py 실행 상태를 확인해 주세요."); }
  if (!response.ok) throw new Error(`로컬 API 오류: ${response.status}`);
  return response.json();
}

function defaultRoster(id){return {character_id:id,owned:false,sequence:0,level:1,build_status:"미육성",max_uses:1,signature_weapon:false,weapon_rank:1};}
function rosterOf(id){return state.roster[id] || (state.roster[id]=defaultRoster(id));}
function escapeHtml(value){return String(value).replace(/[&<>'"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}
function setSaveState(mode,text){const el=$("#saveState");el.className=`save-state ${mode}`;el.querySelector("span").textContent=text;}
function savedLabel(value){if(!value)return "SQLite 저장 준비됨";const d=new Date(value.includes("T")?value:`${value.replace(" ","T")}Z`);return `DB 저장 확인 · ${Number.isNaN(d.getTime())?value:d.toLocaleString("ko-KR",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"})}`;}
function markOwned(){ $("#dialogOwned").checked=true; }

function loadScriptOnce(src){
  return new Promise((resolve,reject)=>{
    const existing=document.querySelector(`script[src="${src}"]`);
    if(existing){existing.dataset.loaded==="true"?resolve():existing.addEventListener("load",resolve,{once:true});return;}
    const script=document.createElement("script");
    script.src=src; script.async=true; script.crossOrigin="anonymous";
    script.addEventListener("load",()=>{script.dataset.loaded="true";resolve();},{once:true});
    script.addEventListener("error",()=>reject(new Error(`Live2D 런타임을 불러오지 못했습니다: ${src}`)),{once:true});
    document.head.appendChild(script);
  });
}

async function ensureSpineRuntime(){
  if(window.PIXI?.spine?.Spine) return;
  if(!state.spineLoading) state.spineLoading=SPINE_SCRIPTS.reduce((p,src)=>p.then(()=>loadScriptOnce(src)),Promise.resolve());
  await state.spineLoading;
}

function clearSpine(){
  if(state.nanokaSpineComponent){
    try{state.nanokaSpineComponent.$destroy();}catch(_){}
    state.nanokaSpineComponent=null;
  }
  if(state.spineApp){
    try{state.spineApp.destroy(true,{children:true,texture:false,baseTexture:false});}catch(_){}
    state.spineApp=null;
  }
  const stage=$("#live2dStage");
  stage?.querySelectorAll("canvas,.nanoka-live2d-host").forEach(node=>node.remove());
}

function fitSpine(spine, app){
  const bounds=spine.getLocalBounds();
  const width=bounds.width||1, height=bounds.height||1;
  const scale=Math.min(app.screen.width/width, app.screen.height/height)*1.08;
  spine.scale.set(scale);
  spine.x=app.screen.width/2-(bounds.x+bounds.width/2)*scale;
  spine.y=app.screen.height/2-(bounds.y+bounds.height/2)*scale+app.screen.height*0.03;
}

function installNanokaAtlasResizeMiddleware(loader){
  const atlasSizes=new Map();
  loader.use((resource,next)=>{
    if(resource.extension==="atlas"||resource.url.includes(".atlas")){
      String(resource.data||"").split(/\r?\n/).forEach(line=>{
        const trimmed=line.trim();
        if(!trimmed) return;
        if(!trimmed.includes(":")){
          atlasSizes.set("__current_page__", trimmed);
          return;
        }
        if(!trimmed.startsWith("size:")) return;
        const page=atlasSizes.get("__current_page__");
        const [rawWidth="0",rawHeight="0"]=trimmed.replace("size:","").split(",").map(value=>value.trim());
        const width=Number(rawWidth), height=Number(rawHeight);
        if(page&&Number.isFinite(width)&&Number.isFinite(height)) atlasSizes.set(page,{width,height});
      });
      next();
      return;
    }
    const image=resource?.data;
    if(!(image instanceof HTMLImageElement||image instanceof HTMLCanvasElement)){
      next();
      return;
    }
    const filename=resource.url.split("/").pop()?.split("?")[0]||"";
    const target=atlasSizes.get(filename);
    if(!target||image.width===target.width&&image.height===target.height){
      next();
      return;
    }
    const canvas=document.createElement("canvas");
    canvas.width=target.width;
    canvas.height=target.height;
    const context=canvas.getContext("2d");
    if(!context){
      next();
      return;
    }
    context.imageSmoothingEnabled=true;
    context.imageSmoothingQuality="high";
    context.drawImage(image,0,0,image.width,image.height,0,0,target.width,target.height);
    resource.data=canvas;
    if(resource.texture?.baseTexture){
      resource.texture.baseTexture.setRealSize(target.width,target.height,1);
      resource.texture.baseTexture.update();
    }
    next();
  });
}

function shouldUseNanokaRenderer(character){
  return character?.live2d_available!==false && Boolean(character?.live2d_skeleton_url || character?.live2d_skeleton_source);
}

async function ensureNanokaSpineModule(){
  if(!state.nanokaSpineModule){
    state.nanokaSpineModule=import("./vendor/nanoka-node5-live2d.js?v=20260711e").catch(error=>{
      state.nanokaSpineModule=null;
      throw error;
    });
  }
  return state.nanokaSpineModule;
}

async function renderNanokaSpine(character, runId, isCurrent){
  const status=$("#live2dStatus"), stage=$("#live2dStage"), fallback=$("#dialogLiveImage");
  const skeletonPath=character.live2d_skeleton_source || character.live2d_skeleton_url;
  const atlasPath=character.live2d_atlas_source || character.live2d_atlas_url;
  if(!skeletonPath||!atlasPath) throw new Error("이 캐릭터의 Live2D 데이터가 없습니다.");
  status.textContent="Live2D 로딩 중…";
  const {NanokaSpinePlayer}=await ensureNanokaSpineModule();
  if(!isCurrent()) throw new Error("stale-live2d-render");
  fallback.hidden=true;
  const host=document.createElement("div");
  host.className="nanoka-live2d-host";
  host.dataset.characterId=character.id;
  stage.appendChild(host);
  state.nanokaSpineComponent=new NanokaSpinePlayer({
    target:host,
    props:{skeletonPath,atlasPath,audioId:"",minScale:.05,maxScale:5}
  });
  await new Promise((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error("Live2D 로딩 시간이 초과되었습니다.")),9000);
    const cleanup=()=>{clearTimeout(timeout);observer.disconnect();};
    const observer=new MutationObserver(()=>{
      if(!isCurrent()){cleanup();reject(new Error("stale-live2d-render"));return;}
      if(stage.querySelector(".nanoka-live2d-host canvas")){
        cleanup();
        requestAnimationFrame(resolve);
      }
    });
    observer.observe(host,{childList:true,subtree:true});
    if(stage.querySelector(".nanoka-live2d-host canvas")){
      cleanup();
      requestAnimationFrame(resolve);
    }
  });
  if(runId!==state.live2dRunId||!isCurrent()) throw new Error("stale-live2d-render");
  status.textContent="";
}

async function renderSpine(character){
  const runId=++state.live2dRunId;
  const isCurrent=()=>state.activeId===character.id&&state.live2dRunId===runId;
  clearSpine();
  const status=$("#live2dStatus"), stage=$("#live2dStage"), fallback=$("#dialogLiveImage");
  fallback.hidden=false;
  status.textContent="Live2D 로딩 중…";
  if(character.live2d_available===false||character.live2d_runtime_supported===false||!character.live2d_skeleton_url||!character.live2d_atlas_url) throw new Error("이 캐릭터의 Live2D 데이터가 없습니다.");
  if(shouldUseNanokaRenderer(character)){
    await renderNanokaSpine(character, runId, isCurrent);
    return;
  }
  await ensureSpineRuntime();
  if(!isCurrent()) throw new Error("stale-live2d-render");
  fallback.hidden=true;
  const PIXI=window.PIXI;
  PIXI.settings.SCALE_MODE=PIXI.SCALE_MODES.LINEAR;
  const app=new PIXI.Application({
    backgroundAlpha:0,
    antialias:true,
    autoDensity:true,
    resolution:Math.min(window.devicePixelRatio||1,3),
    powerPreference:"high-performance",
    resizeTo:stage
  });
  state.spineApp=app;
  stage.appendChild(app.view);
  app.view.className="live2d-canvas";
  await new Promise((resolve,reject)=>{
    let settled=false;
    const cleanup=()=>{clearTimeout(timeout);window.removeEventListener("error",onWindowError);};
    const fail=(error)=>{if(settled)return;settled=true;cleanup();reject(error);};
    const done=()=>{if(settled)return;settled=true;cleanup();resolve();};
    const onWindowError=(event)=>{
      const message=String(event?.error?.stack||event?.message||"");
      if(message.includes("pixi-spine")||message.includes("DataView")||message.includes("SpineParser")) fail(event.error||new Error(message));
    };
    const timeout=setTimeout(()=>fail(new Error("Live2D 로딩 시간이 초과되었습니다.")),6500);
    window.addEventListener("error",onWindowError);
    const loader=new PIXI.Loader();
    installNanokaAtlasResizeMiddleware(loader);
    loader.add("spine-model", character.live2d_skeleton_url, {metadata:{spineAtlasFile:character.live2d_atlas_url}});
    loader.onError.add((error)=>fail(error));
    loader.load((_,resources)=>{
      if(!isCurrent()){fail(new Error("stale-live2d-render"));return;}
      if(!resources["spine-model"]?.spineData){fail(new Error("Spine 데이터를 읽지 못했습니다."));return;}
      const spine=new PIXI.spine.Spine(resources["spine-model"].spineData);
      const idle=spine.spineData.animations.find(a=>a.name==="idle")?.name || spine.spineData.animations[0]?.name;
      if(idle) spine.state.setAnimation(0,idle,true);
      app.stage.addChild(spine);
      window.addEventListener("resize",()=>fitSpine(spine,app),{passive:true});
      requestAnimationFrame(()=>{if(!isCurrent()){fail(new Error("stale-live2d-render"));return;}fitSpine(spine,app); status.textContent=""; done();});
    });
  });
}

function iconFor(type,value){
  const character=state.characters.find(c=>type==="element"?c.element_ko===value:c.weapon_ko===value);
  const src=type==="element"?character?.element_icon:character?.weapon_icon;
  return src?`<img class="filter-icon" src="${imageUrl(src)}" alt="">`:"";
}

function filterChip(type,value,label,icon=""){
  const selected=(type==="element"&&state.filterElement===value)||(type==="weapon"&&state.filterWeapon===value)||(type==="rarity"&&state.filterRarity===value)||(type==="role"&&state.filterRole===value);
  return `<button type="button" class="${selected?"active":""}" data-filter-type="${type}" data-filter-value="${escapeHtml(value)}">${icon}${escapeHtml(label)}</button>`;
}

function renderFilters(){
  const groups=[
    ["속성","element",["",...ELEMENTS],v=>v||"전체",v=>v?iconFor("element",v):""],
    ["무기","weapon",["",...WEAPONS],v=>v||"전체",v=>v?iconFor("weapon",v):""],
    ["레어도","rarity",["","5","4"],v=>v?`${v}★`:"전체",()=>""],
    ["역할","role",["",...ROLES],v=>v||"전체",()=>""],
  ];
  $("#filterPanel").innerHTML=groups.map(([title,type,values,label,icon])=>`
    <section class="filter-group">
      <h3>${title}</h3>
      <div>${values.map(value=>filterChip(type,value,label(value),icon(value))).join("")}</div>
    </section>
  `).join("");
}

function filteredCharacters(){
  const q=$("#searchInput").value.trim().toLowerCase(), element=state.filterElement, weapon=state.filterWeapon, rarity=state.filterRarity, role=state.filterRole, ownedOnly=$("#ownedOnly").checked;
  return state.characters.filter(c=>{
    const r=rosterOf(c.id), hay=`${c.name_ko} ${c.name} ${c.element_ko} ${c.weapon_ko} ${c.role}`.toLowerCase();
    return (!q||hay.includes(q))&&(!element||c.element_ko===element)&&(!weapon||c.weapon_ko===weapon)&&(!rarity||String(c.rarity)===rarity)&&(!role||c.role===role)&&(!ownedOnly||r.owned);
  });
}

function renderGrid(){
  const chars=filteredCharacters();
  $("#emptyState").hidden=chars.length>0;
  $("#characterGrid").innerHTML=chars.map(c=>{
    const r=rosterOf(c.id);
    const elementIcon=c.element_icon?`<img class="mini-icon" src="${imageUrl(c.element_icon)}" alt="" loading="lazy">`:"";
    const weaponIcon=c.weapon_icon?`<img class="mini-icon" src="${imageUrl(c.weapon_icon)}" alt="" loading="lazy">`:"";
    return `<button class="character-card ${r.owned?"owned":""}" data-id="${c.id}" style="--char-color:${COLORS[c.element_ko]}">
      <div class="portrait"><img src="${c.image}" alt="${escapeHtml(c.name_ko)}" loading="lazy" referrerpolicy="no-referrer">${c.preview?`<span style="position:absolute;top:9px;left:9px;background:#15191ee8;border:1px solid #d787e9;color:#f0b7ff;padding:4px 7px;font-size:10px;font-weight:900">PREVIEW ${escapeHtml(c.release_patch||"")}</span>`:""}${r.owned?'<span class="owned-badge">OWNED</span>':''}</div>
      <div class="card-main"><strong>${escapeHtml(c.name_ko)}</strong><div class="meta icon-meta"><span>${elementIcon}${c.element_ko}</span><span>${weaponIcon}${c.weapon_ko}</span><span>${r.owned&&r.signature_weapon?`전무 R${r.weapon_rank}`:`${c.rarity}★`}</span></div></div>
      <div class="card-foot"><span><i class="dot"></i>${r.owned?`S${r.sequence} · Lv.${r.level}`:"미보유"}</span><span>${r.owned?r.build_status:c.role}</span></div>
    </button>`;
  }).join("");
  updateStats();
}

function updateStats(){
  const rows=Object.values(state.roster), owned=rows.filter(r=>r.owned);
  $("#ownedCount").textContent=owned.length;
  $("#readyCount").textContent=owned.filter(r=>["실전 가능","완성"].includes(r.build_status)).length;
  $("#totalCount").textContent=state.characters.length;
}

function openCharacter(id){
  const c=state.characters.find(x=>x.id===id), r=rosterOf(id); state.activeId=id;
  state.live2dRunId++;
  clearSpine();
  const detailImage=c.detail_image || c.image;
  $("#dialogImage").src=detailImage; $("#dialogImage").alt=c.name_ko;
  $("#dialogLiveImage").src=detailImage; $("#dialogLiveImage").alt=`${c.name_ko} Live2D 미리보기`;
  $("#dialogLiveImage").hidden=false;
  $("#live2dStatus").textContent="";
  $("#dialogPortrait").classList.remove("live-mode");
  $("#dialogLiveToggle").setAttribute("aria-pressed","false");
  const hasLive2d=c.live2d_available!==false&&c.live2d_runtime_supported!==false&&Boolean(c.live2d_skeleton_url);
  $("#dialogLiveToggle").textContent=hasLive2d?"일러스트 보기":"Live2D 없음";
  $("#dialogLiveToggle").disabled=!hasLive2d;
  const elementIcon=c.element_icon?`<img class="title-icon" src="${imageUrl(c.element_icon)}" alt="">`:"";
  const weaponIcon=c.weapon_icon?`<img class="title-icon" src="${imageUrl(c.weapon_icon)}" alt="">`:"";
  $("#dialogElement").innerHTML=`${elementIcon}${escapeHtml(c.element_ko.toUpperCase())} · ${escapeHtml(c.role)}${c.preview?` · ${escapeHtml(c.release_patch)} 프리뷰`:""}`;
  $("#dialogName").textContent=c.name_ko; $("#dialogMeta").textContent=`${c.weapon_ko} · ${c.rarity}성 · ${c.name}`;
  if(weaponIcon) $("#dialogMeta").innerHTML=`${weaponIcon}${escapeHtml(c.weapon_ko)} · ${c.rarity}성 · ${escapeHtml(c.name)}`;
  $("#dialogOwned").checked=Boolean(r.owned); $("#dialogSequence").value=r.sequence; $("#dialogLevel").value=r.level;
  $("#dialogBuild").value=r.build_status; $("#dialogUses").value=r.max_uses ?? 1;
  $("#dialogSignature").checked=Boolean(r.signature_weapon); $("#dialogWeaponRank").value=r.weapon_rank ?? 1;
  $("#characterDialog").showModal();
  if(hasLive2d) requestAnimationFrame(()=>toggleLive2d(true));
}

async function toggleLive2d(force){
  const portrait=$("#dialogPortrait");
  const enabled=typeof force==="boolean"?force:!portrait.classList.contains("live-mode");
  portrait.classList.toggle("live-mode", enabled);
  $("#dialogLiveToggle").setAttribute("aria-pressed", String(enabled));
  $("#dialogLiveToggle").textContent=enabled?"일러스트 보기":"Live2D 보기";
  if(!enabled){state.live2dRunId++;clearSpine();$("#dialogLiveImage").hidden=false;$("#live2dStatus").textContent="";return;}
  const character=state.characters.find(x=>x.id===state.activeId);
  try{await renderSpine(character);}
  catch(error){
    if(character?.id!==state.activeId)return;
    if(String(error?.message||error)!=="stale-live2d-render"){
      character.live2d_runtime_supported=false;
      clearSpine();
      $("#dialogPortrait").classList.remove("live-mode");
      $("#dialogLiveToggle").setAttribute("aria-pressed","false");
      $("#dialogLiveToggle").textContent="Live2D 없음";
      $("#dialogLiveToggle").disabled=true;
      $("#live2dStatus").textContent="현재 런타임에서 Live2D를 표시할 수 없어 일러스트로 표시 중";
      $("#dialogLiveImage").hidden=false;
      console.warn(error);
    }
  }
}

async function saveActive(event){
  event.preventDefault(); const r=rosterOf(state.activeId);
  Object.assign(r,{owned:$("#dialogOwned").checked,sequence:+$("#dialogSequence").value,level:+$("#dialogLevel").value,build_status:$("#dialogBuild").value,max_uses:+$("#dialogUses").value,signature_weapon:$("#dialogSignature").checked,weapon_rank:+$("#dialogWeaponRank").value});
  setSaveState("saving","SQLite에 저장 중…");
  try{const result=await api("/api/roster",{method:"POST",body:JSON.stringify([r])});setSaveState("saved",savedLabel(result.saved_at));$("#characterDialog").close();renderGrid();toast("캐릭터 설정을 DB에 저장했습니다.");}
  catch(error){setSaveState("error","저장 실패 · 다시 시도해 주세요");toast(error.message);}
}

async function recommend(){
  const button=$("#recommendButton"); button.disabled=true; button.textContent="구성 계산 중…";
  try{
    const result=await api("/api/recommend",{method:"POST",body:JSON.stringify({team_count:$("#teamCount").value,roster:state.roster})});
    $("#recommendMessage").textContent=result.message;
    const teamCard=t=>`<article class="team-card"><div class="team-head"><h3>TEAM ${String(t.id).padStart(2,"0")} <small>${escapeHtml(t.confidence)} 신뢰도 · 육성 ${t.readiness}%</small></h3><span class="score">${t.score}</span></div><div class="team-members">${t.members.map(m=>`<div class="member"><img src="${imageUrl(m.image)}" alt="${escapeHtml(m.name_ko)}" referrerpolicy="no-referrer"><div><strong>${escapeHtml(m.name_ko)}</strong><small>${escapeHtml(m.slot||m.role)}</small></div></div>`).join("")}</div><div class="team-tags">${(t.tags||[]).map(tag=>`<span>${escapeHtml(tag)}</span>`).join("")}</div><p class="team-reason">${escapeHtml(t.reason)}</p>${t.score_details?`<p class="team-reason">조합 ${t.score_details.composition} · 최신성 ${t.score_details.meta} · 돌파/무기 ${t.score_details.investment} · 육성 ${t.score_details.build}</p>`:""}</article>`;
    $("#teamResults").innerHTML=result.configurations?.length?result.configurations.map((config,index)=>`<section class="configuration"><div class="configuration-head"><div><span>ALTERNATIVE ${String(index+1).padStart(2,"0")}</span><h2>${escapeHtml(config.label)}</h2></div><p>${config.team_count}개 파티 · 조합 지수 ${config.total_score} · 전투 점수 ${config.combat_score}</p></div><div class="configuration-teams">${config.teams.map(teamCard).join("")}</div></section>`).join(""):`<div class="empty">${escapeHtml(result.message)}</div>`;
  }catch(error){$("#recommendMessage").textContent=error.message;$("#teamResults").innerHTML=`<div class="empty">${escapeHtml(error.message)}</div>`;toast(error.message);}
  finally{button.disabled=false;button.textContent="✦ 자동 파티 구성";}
}

function toast(message){const el=$("#toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),1800);}
function showView(view){const roster=view==="roster";$("#rosterView").hidden=!roster;$("#plannerView").hidden=roster;document.querySelectorAll(".nav-link").forEach(x=>x.classList.toggle("active",x.dataset.view===view));}

async function init(){
  for(let i=0;i<=6;i++) $("#dialogSequence").insertAdjacentHTML("beforeend",`<option value="${i}">S${i}</option>`);
  const [characters,roster,storage]=await Promise.all([api("/api/characters"),api("/api/roster"),api("/api/storage")]); state.characters=characters.map(c=>({...c,image:imageUrl(c.image),detail_image:imageUrl(c.detail_image),element_icon:imageUrl(c.element_icon),weapon_icon:imageUrl(c.weapon_icon)})); state.roster=roster;setSaveState("saved",savedLabel(storage.last_saved));
  renderFilters();renderGrid();
  ["#searchInput","#ownedOnly"].forEach(s=>$(s).addEventListener("input",renderGrid));
  $("#filterPanel").addEventListener("click",e=>{
    const button=e.target.closest("[data-filter-type]");
    if(!button)return;
    const type=button.dataset.filterType, value=button.dataset.filterValue;
    if(type==="element")state.filterElement=value;
    if(type==="weapon")state.filterWeapon=value;
    if(type==="rarity")state.filterRarity=value;
    if(type==="role")state.filterRole=value;
    renderFilters();renderGrid();
  });
  $("#characterGrid").addEventListener("click",e=>{const card=e.target.closest("[data-id]");if(card)openCharacter(card.dataset.id);});
  $("#saveCharacter").addEventListener("click",saveActive);$("#recommendButton").addEventListener("click",recommend);$("#dialogLiveToggle").addEventListener("click",toggleLive2d);
  ["#dialogSequence","#dialogLevel","#dialogBuild","#dialogUses","#dialogSignature","#dialogWeaponRank"].forEach(s=>$(s).addEventListener("input",markOwned));
  $("#maxLevel").addEventListener("click",()=>{$("#dialogLevel").value=90;markOwned();});
  document.querySelectorAll(".nav-link").forEach(x=>x.addEventListener("click",()=>showView(x.dataset.view)));
}

init().catch(error=>{setSaveState("error","로컬 서버 연결 필요");$("#characterGrid").innerHTML=`<div class="empty">앱을 불러오지 못했습니다: ${escapeHtml(error.message)}<br><br>터미널에서 <b>python3 server.py</b>를 실행해 주세요.</div>`;console.error(error);});
