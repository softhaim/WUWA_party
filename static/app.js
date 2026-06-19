const state = { characters: [], roster: {}, filterElement: "", activeId: null };
const COLORS = {응결:"#173849",용융:"#4c2520",전도:"#312548",기류:"#193d36",회절:"#4a4120",인멸:"#3d2545"};
const $ = (selector) => document.querySelector(selector);

async function api(path, options={}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json"}, ...options});
  if (!response.ok) throw new Error(`API 오류: ${response.status}`);
  return response.json();
}

function defaultRoster(id){return {character_id:id,owned:false,sequence:0,level:1,build_status:"미육성",max_uses:1,signature_weapon:false,weapon_rank:1};}
function rosterOf(id){return state.roster[id] || (state.roster[id]=defaultRoster(id));}
function escapeHtml(value){return String(value).replace(/[&<>'"]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));}
function setSaveState(mode,text){const el=$("#saveState");el.className=`save-state ${mode}`;el.querySelector("span").textContent=text;}
function savedLabel(value){if(!value)return "SQLite 저장 준비됨";const d=new Date(value.includes("T")?value:`${value.replace(" ","T")}Z`);return `DB 저장 확인 · ${Number.isNaN(d.getTime())?value:d.toLocaleString("ko-KR",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit"})}`;}
function markOwned(){ $("#dialogOwned").checked=true; }

function renderTabs(){
  const tabs=["전체","응결","용융","전도","기류","회절","인멸"];
  $("#elementTabs").innerHTML=tabs.map(x=>`<button class="${(x==="전체"&&!state.filterElement)||x===state.filterElement?"active":""}" data-element="${x}">${x}</button>`).join("");
}

function filteredCharacters(){
  const q=$("#searchInput").value.trim().toLowerCase(), element=$("#elementFilter").value||state.filterElement, weapon=$("#weaponFilter").value, ownedOnly=$("#ownedOnly").checked;
  return state.characters.filter(c=>{
    const r=rosterOf(c.id), hay=`${c.name_ko} ${c.name} ${c.element_ko} ${c.weapon_ko} ${c.role}`.toLowerCase();
    return (!q||hay.includes(q))&&(!element||c.element_ko===element)&&(!weapon||c.weapon_ko===weapon)&&(!ownedOnly||r.owned);
  });
}

function renderGrid(){
  const chars=filteredCharacters();
  $("#emptyState").hidden=chars.length>0;
  $("#characterGrid").innerHTML=chars.map(c=>{
    const r=rosterOf(c.id);
    return `<button class="character-card ${r.owned?"owned":""}" data-id="${c.id}" style="--char-color:${COLORS[c.element_ko]}">
      <div class="portrait"><img src="${c.image}" alt="${escapeHtml(c.name_ko)}" loading="lazy" referrerpolicy="no-referrer">${r.owned?'<span class="owned-badge">OWNED</span>':''}</div>
      <div class="card-main"><strong>${escapeHtml(c.name_ko)}</strong><div class="meta"><span>${c.element_ko} · ${c.weapon_ko}</span><span>${r.owned&&r.signature_weapon?`전무 R${r.weapon_rank}`:`${c.rarity}★`}</span></div></div>
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
  $("#dialogImage").src=c.image; $("#dialogImage").alt=c.name_ko; $("#dialogElement").textContent=`${c.element_ko.toUpperCase()} · ${c.role}`;
  $("#dialogName").textContent=c.name_ko; $("#dialogMeta").textContent=`${c.weapon_ko} · ${c.rarity}성 · ${c.name}`;
  $("#dialogOwned").checked=Boolean(r.owned); $("#dialogSequence").value=r.sequence; $("#dialogLevel").value=r.level;
  $("#dialogBuild").value=r.build_status; $("#dialogUses").value=r.max_uses ?? 1;
  $("#dialogSignature").checked=Boolean(r.signature_weapon); $("#dialogWeaponRank").value=r.weapon_rank ?? 1;
  $("#characterDialog").showModal();
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
    const teamCard=t=>`<article class="team-card"><div class="team-head"><h3>TEAM ${String(t.id).padStart(2,"0")} <small>${escapeHtml(t.confidence)} 신뢰도 · 육성 ${t.readiness}%</small></h3><span class="score">${t.score}</span></div><div class="team-members">${t.members.map(m=>`<div class="member"><img src="${m.image}" alt="${escapeHtml(m.name_ko)}" referrerpolicy="no-referrer"><div><strong>${escapeHtml(m.name_ko)}</strong><small>${escapeHtml(m.slot||m.role)}</small></div></div>`).join("")}</div><div class="team-tags">${(t.tags||[]).map(tag=>`<span>${escapeHtml(tag)}</span>`).join("")}</div><p class="team-reason">${escapeHtml(t.reason)}</p></article>`;
    $("#teamResults").innerHTML=result.configurations?.length?result.configurations.map((config,index)=>`<section class="configuration"><div class="configuration-head"><div><span>ALTERNATIVE ${String(index+1).padStart(2,"0")}</span><h2>${escapeHtml(config.label)}</h2></div><p>${config.team_count}개 파티 · 조합 지수 ${config.total_score} · 전투 점수 ${config.combat_score}</p></div><div class="configuration-teams">${config.teams.map(teamCard).join("")}</div></section>`).join(""):`<div class="empty">${escapeHtml(result.message)}</div>`;
  }finally{button.disabled=false;button.textContent="✦ 자동 파티 구성";}
}

function toast(message){const el=$("#toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),1800);}
function showView(view){const roster=view==="roster";$("#rosterView").hidden=!roster;$("#plannerView").hidden=roster;document.querySelectorAll(".nav-link").forEach(x=>x.classList.toggle("active",x.dataset.view===view));}

async function init(){
  for(let i=0;i<=6;i++) $("#dialogSequence").insertAdjacentHTML("beforeend",`<option value="${i}">S${i}</option>`);
  const [characters,roster,storage]=await Promise.all([api("/api/characters"),api("/api/roster"),api("/api/storage")]); state.characters=characters; state.roster=roster;setSaveState("saved",savedLabel(storage.last_saved));
  renderTabs();renderGrid();
  ["#searchInput","#elementFilter","#weaponFilter","#ownedOnly"].forEach(s=>$(s).addEventListener("input",renderGrid));
  $("#elementTabs").addEventListener("click",e=>{if(!e.target.dataset.element)return;state.filterElement=e.target.dataset.element==="전체"?"":e.target.dataset.element;$("#elementFilter").value=state.filterElement;renderTabs();renderGrid();});
  $("#characterGrid").addEventListener("click",e=>{const card=e.target.closest("[data-id]");if(card)openCharacter(card.dataset.id);});
  $("#saveCharacter").addEventListener("click",saveActive);$("#recommendButton").addEventListener("click",recommend);
  ["#dialogSequence","#dialogLevel","#dialogBuild","#dialogUses","#dialogSignature","#dialogWeaponRank"].forEach(s=>$(s).addEventListener("input",markOwned));
  $("#maxLevel").addEventListener("click",()=>{$("#dialogLevel").value=90;markOwned();});
  document.querySelectorAll(".nav-link").forEach(x=>x.addEventListener("click",()=>showView(x.dataset.view)));
}

init().catch(error=>{$("#characterGrid").innerHTML=`<div class="empty">앱을 불러오지 못했습니다: ${escapeHtml(error.message)}</div>`;console.error(error);});
