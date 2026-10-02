const BUILD_POINTS={"미육성":0,"육성 중":8,"실전 가능":18,"완성":25};
const BUILD_READINESS={"미육성":0,"육성 중":.45,"실전 가능":.78,"완성":1};
const SEQUENCE_QUALITY=[.78,.83,.87,.91,.94,.97,1];
const SCORE_WEIGHTS={composition:43,meta:19,investment:20,build:18};
const TIER_META_VALUE={T0:10,"T0.5":9,T1:8,"T1.5":7,T2:6,T3:4.5,T4:3};
const TIER_CARRY_PRIORITY={T0:115,"T0.5":100,T1:84,"T1.5":70,T2:58,T3:38,T4:25};
const SEQUENCE_PRIORITY=[0,6,15,28,38,49,60];
const SHARED_USAGE={"rover-aero":"rover","rover-electro":"rover","rover-havoc":"rover","rover-spectro":"rover"};
const POSITION_ORDER={carry:0,amplifier:1,support:2};
const SLOT_NAMES={carry:"메인 딜러",amplifier:"서브 딜러",support:"서포터"};

const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
const round1=value=>Math.round(value*10)/10;
const usageKey=id=>SHARED_USAGE[id]||id;
const setIntersects=(a,b)=>[...a].some(value=>b.has(value));

function profileFor(character,rules){
  const explicit=rules.profiles?.[character.id];
  const position=explicit?.position||{"딜러":"carry","서브딜러":"amplifier","서포터":"support"}[character.role]||"amplifier";
  const profile=explicit?{...explicit}:{position,archetypes:[character.element_ko]};
  if(!explicit&&position==="carry")profile.damage=[character.element_ko];
  else if(!explicit)profile.provides=[character.element_ko];
  if(!explicit&&position==="support")profile.sustain=true;
  const metaTier=rules.carry_meta_tiers?.[character.id];
  if(metaTier){profile.meta_tier=metaTier;profile.meta_value=TIER_META_VALUE[metaTier]??profile.meta_value??5;}
  return profile;
}

function readiness(member){
  const state=member.state;
  let value=BUILD_READINESS[state.build_status]||0;
  let floor=state.level>=90?.55:state.level>=80?.42:state.level>=70?.28:0;
  if(state.signature_weapon)floor=Math.min(.68,floor+.1);
  return Math.max(value,floor);
}

function investment(member){
  const state=member.state;
  let value=SEQUENCE_QUALITY[clamp(Number(state.sequence)||0,0,6)];
  if(state.signature_weapon)value+=.12+Math.max(0,(Number(state.weapon_rank)||1)-1)*.025;
  return Math.min(1,value);
}

function carryPriority(member,profile){
  const state=member.state,tier=profile.meta_tier;
  const baseline=TIER_CARRY_PRIORITY[tier]??(profile.meta_value||5)*9;
  return baseline+SEQUENCE_PRIORITY[clamp(Number(state.sequence)||0,0,6)]+(state.signature_weapon?4:0)+Math.max(0,(Number(state.weapon_rank)||1)-1)*1.5;
}

function weightedAverage(members,positions,values){
  const weights={carry:.5,amplifier:.3,support:.2};
  let total=0, weight=0;
  for(const member of members){const w=weights[positions[member.id]]||.25;total+=values[member.id]*w;weight+=w;}
  return total/Math.max(.01,weight);
}

function evaluateTeam(members,rules,templateMap){
  const ids=members.map(member=>member.id);
  if(new Set(members.map(member=>member.usage_key)).size!==members.length)return null;
  const key=[...ids].sort().join(":");
  const template=templateMap.get(key);
  const profiles=Object.fromEntries(members.map(member=>[member.id,profileFor(member,rules)]));
  const carries=members.filter(member=>profiles[member.id].position==="carry");
  if(!carries.length)return null;
  const positions=Object.fromEntries(members.map(member=>[member.id,template?.positions?.[member.id]||profiles[member.id].position||"amplifier"]));
  const ready={},invested={};
  for(const member of members){
    let value=readiness(member);
    if(member.state.build_status==="미육성")value=Math.min(value,positions[member.id]==="carry"?.35:positions[member.id]==="amplifier"?.65:value);
    ready[member.id]=value;invested[member.id]=investment(member);
  }
  const core=members.filter(member=>positions[member.id]!=="support");
  const coreReadiness=core.reduce((sum,member)=>sum+ready[member.id],0)/Math.max(1,core.length);
  const weakestCore=Math.min(...core.map(member=>ready[member.id]));
  let reason,tags,confidence,rawScore=0;
  if(template){
    const preview=template.status==="preview";
    const early=template.status==="early";
    reason=`${preview?"출시 전 프리뷰":early?"출시 초기 조합":"메타 조합"} · ${template.label}`;
    tags=template.tags||[];confidence=preview?"프리뷰":early?"초기 검증":"높음";
  }else{
    const carry=carries.reduce((best,item)=>(profiles[item.id].meta_value||5)>(profiles[best.id].meta_value||5)?item:best,carries[0]);
    const damage=new Set(profiles[carry.id].damage||[]), archetypes=new Set(profiles[carry.id].archetypes||[]);
    const buffs=new Set(),hits=new Set();let synergy=0;
    for(const member of members){if(member.id===carry.id)continue;const p=profiles[member.id];for(const value of p.provides||[])if(damage.has(value))buffs.add(value);for(const value of p.archetypes||[])if(archetypes.has(value))hits.add(value);if((carry.synergy||[]).includes(member.id))synergy++;}
    const amplifiers=members.filter(member=>profiles[member.id].position==="amplifier");
    if(!amplifiers.length||(!buffs.size&&!hits.size&&!synergy))return null;
    const supportLeverage=members.filter(member=>profiles[member.id].position==="support").reduce((sum,member)=>sum+(profiles[member.id].support_value||3)*coreReadiness*1.2,0);
    const averagePower=members.reduce((sum,member)=>sum+member.power,0)/members.length;
    const readinessPenalty=members.reduce((sum,member)=>sum+(1-ready[member.id]),0)*8;
    const supportCount=members.filter(member=>profiles[member.id].position==="support").length;
    rawScore=Math.min(91,38+averagePower*.72+buffs.size*9+hits.size*5+synergy*4+(members.some(member=>profiles[member.id].sustain)?5:0)+supportLeverage-readinessPenalty-Math.max(0,carries.length-1)*3-Math.max(0,supportCount-1)*8);
    tags=[...new Set([...buffs,...hits])].sort();reason=`호환 조합 · ${carry.name_ko}의 ${tags.join(", ")||"육성도와 속성"} 조건을 공유`;confidence=tags.length?"중간":"낮음";
  }
  const primary=carries.reduce((best,item)=>(profiles[item.id].meta_value||5)>(profiles[best.id].meta_value||5)?item:best,carries[0]);
  const details={
    composition:round1((template?template.score:Math.min(88,rawScore))/100*SCORE_WEIGHTS.composition),
    meta:round1(Math.min(1,(profiles[primary.id].meta_value||5)/10)*SCORE_WEIGHTS.meta),
    investment:round1(weightedAverage(members,positions,invested)*SCORE_WEIGHTS.investment),
    build:round1(weightedAverage(members,positions,ready)*SCORE_WEIGHTS.build)
  };
  const score=round1(Math.min(100,Object.values(details).reduce((a,b)=>a+b,0)));
  const highEnd=new Set([...(rules.high_end_cores||[]),...(rules.preview_high_end_cores||[])].map(core=>[...core].sort().join(":")));
  const tier=highEnd.has(key)?"bis":template?.score>=95?"high":template?.score>=90?"alternative":template?.tier;
  let allocation=score+(template?3:0)+({bis:10,high:7,alternative:3,expansion:0}[tier]||0);
  if(template&&["3.5","3.5-beta","3.6","3.6-beta","3.7","3.7-beta"].includes(template.patch)&&tier==="bis")allocation+=1;
  const premium=Math.max(0,...members.filter(member=>positions[member.id]==="support").map(member=>profiles[member.id].support_value||0));
  if(premium>=8&&weakestCore<.7)allocation-=(.7-weakestCore)*premium*2.8;
  const primaryCarryPriority=carryPriority(primary,profiles[primary.id]);
  const carryInvestment=Math.max(...carries.map(member=>((profiles[member.id].meta_value||5)*.8+(Number(member.state.sequence)||0)*2+(member.state.signature_weapon?1.5:0))*ready[member.id]));
  allocation+=carryInvestment+primaryCarryPriority*.25;
  return {key,members,score,allocation_score:round1(allocation),reason,tags,confidence,readiness:Math.round(Object.values(ready).reduce((a,b)=>a+b,0)/members.length*100),score_details:details,member_positions:template?.positions||{},effective_tier:tier,primary_carry_id:primary.id,carry_investment:round1(carryInvestment),carry_priority:round1(primaryCarryPriority),premium_core_mismatch:premium>=8&&weakestCore<.45,verified_template:Boolean(template),template_id:template?.id,template_score:template?.score,meta_tier:template?.meta_tier||profiles[primary.id].meta_tier};
}

function applyOpportunity(candidates){
  const byCarry=new Map(),memberCarries=new Map();
  for(const candidate of candidates){if(!byCarry.has(candidate.primary_carry_id))byCarry.set(candidate.primary_carry_id,[]);byCarry.get(candidate.primary_carry_id).push(candidate);for(const member of candidate.members){if(member.id===candidate.primary_carry_id)continue;if(!memberCarries.has(member.id))memberCarries.set(member.id,new Set());memberCarries.get(member.id).add(candidate.primary_carry_id);}}
  for(const candidate of candidates){let bestLoss=0;for(const member of candidate.members){const position=candidate.member_positions[member.id]||member._position;if(member.id===candidate.primary_carry_id||position!=="support"||(memberCarries.get(member.id)?.size||0)<2)continue;const alternatives=(byCarry.get(candidate.primary_carry_id)||[]).filter(team=>!team.members.some(item=>item.id===member.id));if(!alternatives.length)continue;let loss=Math.max(0,candidate.score-Math.max(...alternatives.map(team=>team.score)));if(candidate.effective_tier==="bis"&&alternatives.some(team=>team.effective_tier==="bis"&&candidate.score-team.score<=1.5))loss=0;bestLoss=Math.max(bestLoss,loss);}candidate.allocation_score=round1(candidate.allocation_score+bestLoss*(2+candidate.carry_investment/10));}
}

function applyCarryResourcePriority(candidates){
  const byCarry=new Map(),claims=new Map(),candidateClaims=new Map();
  for(const candidate of candidates){if(!byCarry.has(candidate.primary_carry_id))byCarry.set(candidate.primary_carry_id,[]);byCarry.get(candidate.primary_carry_id).push(candidate);}
  for(const candidate of candidates){
    if(!candidate.verified_template||Number(candidate.template_score||0)<90)continue;
    for(const member of candidate.members){
      if(member.id===candidate.primary_carry_id)continue;
      const alternatives=(byCarry.get(candidate.primary_carry_id)||[]).filter(team=>!team.members.some(item=>item.usage_key===member.usage_key));
      const bestAlternative=alternatives.length?Math.max(...alternatives.map(team=>team.score)):candidate.score-6;
      let loss=Math.max(0,candidate.score-bestAlternative);
      const interchangeable=candidate.effective_tier==="bis"&&alternatives.some(team=>team.effective_tier==="bis"&&candidate.score-team.score<=1.5);
      if(interchangeable)loss=0;
      const claim=(candidate.carry_priority||0)-(interchangeable?24:0)+loss*4,key=`${candidate.key}|${member.usage_key}`;
      candidateClaims.set(key,claim);
      if(!claims.has(member.usage_key))claims.set(member.usage_key,new Map());
      const carryClaims=claims.get(member.usage_key),carryId=candidate.primary_carry_id;
      carryClaims.set(carryId,Math.max(carryClaims.get(carryId)??-Infinity,claim));
    }
  }
  for(const candidate of candidates){
    let penalty=0;
    for(const member of candidate.members){
      if(member.id===candidate.primary_carry_id)continue;
      const own=candidateClaims.get(`${candidate.key}|${member.usage_key}`)??candidate.carry_priority??0;
      const ranked=[...(claims.get(member.usage_key)?.values()||[own])].sort((a,b)=>b-a),limit=Math.max(1,Number(member._usage_limit)||1),cutoff=ranked[Math.min(limit,ranked.length)-1];
      if(own<cutoff)penalty+=(cutoff-own)*.9;
    }
    penalty=Math.min(15,penalty);
    candidate.resource_priority_penalty=round1(penalty);candidate.resource_priority_bonus=0;
    candidate.allocation_score=round1(candidate.allocation_score-penalty);
  }
}

function optimize(candidates,count,alternatives=3){
  let states=[{teams:[],counts:{},total:0}];const width=count>4?1500:450;
  for(let depth=0;depth<count;depth++){
    const expanded=[];
    for(const state of states){const selected=new Set(state.teams.map(team=>team.key));for(const candidate of candidates){if(selected.has(candidate.key))continue;const counts={...state.counts};let allowed=true;for(const member of candidate.members){counts[member.usage_key]=(counts[member.usage_key]||0)+1;if(counts[member.usage_key]>member._usage_limit){allowed=false;break;}}if(allowed)expanded.push({teams:[...state.teams,candidate],counts,total:state.total+candidate.allocation_score+Object.keys(counts).length*.15});}}
    if(!expanded.length)break;expanded.sort((a,b)=>b.total-a.total);states=expanded.slice(0,width);
  }
  states.sort((a,b)=>b.teams.length-a.teams.length||b.total-a.total);const seen=new Set(),result=[];
  for(const state of states){const key=state.teams.map(team=>team.key).sort().join("|");if(seen.has(key))continue;seen.add(key);result.push(state.teams);if(result.length>=alternatives)break;}
  return result;
}

function optimizeComplete(candidates,limit,alternatives=3){
  let states=[{teams:[],counts:{},total:0}],deepest=states;const width=3000;
  for(let depth=0;depth<limit;depth++){
    const expanded=[];
    for(const state of states){
      const selected=new Set(state.teams.map(team=>team.key));
      for(const candidate of candidates){
        if(selected.has(candidate.key))continue;
        const counts={...state.counts};let allowed=true;
        for(const member of candidate.members){counts[member.usage_key]=(counts[member.usage_key]||0)+1;if(counts[member.usage_key]>member._usage_limit){allowed=false;break;}}
        if(allowed)expanded.push({teams:[...state.teams,candidate],counts,total:state.total+candidate.allocation_score});
      }
    }
    if(!expanded.length)break;
    expanded.sort((a,b)=>b.total-a.total);states=expanded.slice(0,width);deepest=states;
  }
  deepest.sort((a,b)=>b.total-a.total);
  const unique=[],seen=new Set();for(const state of deepest){const key=state.teams.map(team=>team.key).sort().join("||");if(seen.has(key))continue;seen.add(key);unique.push(state);}
  if(!unique.length)return [];
  const primaryCarries=new Set(unique[0].teams.map(team=>team.primary_carry_id));
  const greedyForced=seed=>{
    const teams=[seed],counts={};for(const member of seed.members)counts[member.usage_key]=(counts[member.usage_key]||0)+1;
    while(teams.length<limit){
      const keys=new Set(teams.map(team=>team.key));
      const feasible=candidates.filter(candidate=>!keys.has(candidate.key)&&candidate.members.every(member=>(counts[member.usage_key]||0)+1<=member._usage_limit));
      if(!feasible.length)break;
      let chosen=null,bestFuture=-1,bestScore=-Infinity;
      for(const candidate of feasible){
        const next={...counts};for(const member of candidate.members)next[member.usage_key]=(next[member.usage_key]||0)+1;
        const futureCarries=new Set(feasible.filter(future=>future.key!==candidate.key&&future.members.every(member=>(next[member.usage_key]||0)+1<=member._usage_limit)).map(future=>future.primary_carry_id)).size;
        if(futureCarries>bestFuture||(futureCarries===bestFuture&&candidate.allocation_score>bestScore)){chosen=candidate;bestFuture=futureCarries;bestScore=candidate.allocation_score;}
      }
      teams.push(chosen);for(const member of chosen.members)counts[member.usage_key]=(counts[member.usage_key]||0)+1;
    }
    return teams;
  };
  const bestByCarry=new Map();for(const candidate of candidates){if(primaryCarries.has(candidate.primary_carry_id))continue;const current=bestByCarry.get(candidate.primary_carry_id);if(!current||candidate.allocation_score>current.allocation_score)bestByCarry.set(candidate.primary_carry_id,candidate);}
  for(const seed of bestByCarry.values()){const teams=greedyForced(seed);if(teams.length!==unique[0].teams.length)continue;const key=teams.map(team=>team.key).sort().join("||");if(seen.has(key))continue;seen.add(key);unique.push({teams,total:teams.reduce((sum,team)=>sum+team.allocation_score,0)});}
  const result=[unique.shift().teams],covered=new Set(result[0].map(team=>team.primary_carry_id));
  while(unique.length&&result.length<alternatives){
    let best=0,bestNew=-1,bestTotal=-Infinity;
    for(let index=0;index<unique.length;index++){const newCarries=new Set(unique[index].teams.map(team=>team.primary_carry_id).filter(id=>!covered.has(id))).size;if(newCarries>bestNew||(newCarries===bestNew&&unique[index].total>bestTotal)){best=index;bestNew=newCarries;bestTotal=unique[index].total;}}
    const state=unique.splice(best,1)[0];result.push(state.teams);for(const team of state.teams)covered.add(team.primary_carry_id);
  }
  return result;
}

function completeAllocation(candidates,available,count,excludedKey=null){
  const selected=[],counts={},keys=new Set(),limits={},positions={};
  for(const member of available){
    limits[member.usage_key]=Math.max(limits[member.usage_key]||0,member._usage_limit);
    (positions[member.usage_key]??=new Set()).add(member._position);
  }
  for(let depth=0;depth<count;depth++){
    const teamsLeft=count-depth-1, viable=[];
    for(const candidate of candidates){
      if(candidate.key===excludedKey||keys.has(candidate.key))continue;
      const next={...counts};let allowed=true;
      for(const member of candidate.members){next[member.usage_key]=(next[member.usage_key]||0)+1;if(next[member.usage_key]>limits[member.usage_key]){allowed=false;break;}}
      if(!allowed)continue;
      const remainingTotal=Object.keys(limits).reduce((sum,id)=>sum+limits[id]-(next[id]||0),0);
      const remainingCarries=Object.keys(limits).reduce((sum,id)=>sum+(positions[id].has("carry")?limits[id]-(next[id]||0):0),0);
      if(remainingTotal>=teamsLeft*3&&remainingCarries>=teamsLeft)viable.push(candidate);
    }
    if(!viable.length)break;
    const chosen=viable[0];selected.push(chosen);keys.add(chosen.key);
    for(const member of chosen.members)counts[member.usage_key]=(counts[member.usage_key]||0)+1;
  }
  return selected;
}

function extendAllocation(candidates,seed,count){
  const selected=[...seed],keys=new Set(seed.map(team=>team.key)),counts={};
  for(const team of seed)for(const member of team.members)counts[member.usage_key]=(counts[member.usage_key]||0)+1;
  while(selected.length<count){
    const next=candidates.find(candidate=>!keys.has(candidate.key)&&candidate.members.every(member=>(counts[member.usage_key]||0)<member._usage_limit));
    if(!next)break;
    selected.push(next);keys.add(next.key);for(const member of next.members)counts[member.usage_key]=(counts[member.usage_key]||0)+1;
  }
  return selected;
}

function serialize(teams,rules){
  return [...teams].sort((a,b)=>b.score-a.score).map((team,index)=>({id:index+1,score:team.score,members:[...team.members].sort((a,b)=>POSITION_ORDER[team.member_positions[a.id]||a._position]-POSITION_ORDER[team.member_positions[b.id]||b._position]).map(member=>({id:member.id,name_ko:member.name_ko,image:member.image,role:member.role,element_ko:member.element_ko,slot:SLOT_NAMES[team.member_positions[member.id]||member._position]||member.role})),reason:team.reason,tags:team.tags,confidence:team.confidence,readiness:team.readiness,score_details:team.score_details,verified_template:team.verified_template,template_id:team.template_id,meta_tier:team.meta_tier}));
}

export function recommendInBrowser({characters,rules,roster,team_count=3,allow_inferred=false}){
  const available=[];
  for(const [id,state] of Object.entries(roster||{})){
    const character=characters.find(item=>item.id===id);if(!character||!state.owned||Number(state.max_uses||1)<=0)continue;
    const member={...character,state:{...state,level:Number(state.level)||1,sequence:Number(state.sequence)||0,weapon_rank:Number(state.weapon_rank)||1},usage_key:usageKey(id)};
    member._position=profileFor(member,rules).position;member.power=(BUILD_POINTS[state.build_status]||0)+member.state.level/10+member.state.sequence*.7+(state.signature_weapon?4:0)+member.state.weapon_rank*.6;available.push(member);
  }
  if(available.length<3)return {teams:[],configurations:[],message:"추천을 받으려면 사용할 캐릭터를 3명 이상 보유로 설정해 주세요."};
  const limits={};for(const member of available)limits[member.usage_key]=Math.max(limits[member.usage_key]||0,Number(member.state.max_uses)||1);for(const member of available)member._usage_limit=limits[member.usage_key];
  const maximum=Math.max(1,Math.floor(Object.values(limits).reduce((a,b)=>a+b,0)/3));const requested=String(team_count)==="all"?maximum:clamp(Number(team_count)||3,1,maximum);
  const templateMap=new Map((rules.templates||[]).map(template=>[[...template.members].sort().join(":"),template]));const candidates=[];
  for(let a=0;a<available.length-2;a++)for(let b=a+1;b<available.length-1;b++)for(let c=b+1;c<available.length;c++){const team=evaluateTeam([available[a],available[b],available[c]],rules,templateMap);if(team&&(allow_inferred||team.verified_template)&&(!team.premium_core_mismatch||String(team_count)!=="all")&&(String(team_count)!=="all"||Number(team.template_score||0)>=80))candidates.push(team);}
  // A fully owned catalog produces tens of thousands of mechanically possible
  // triples. Opportunity-cost comparison is quadratic, so first retain the
  // strongest teams plus broad per-character coverage. This preserves roster
  // expansion while keeping the worker responsive on mobile devices.
  candidates.sort((a,b)=>b.allocation_score-a.allocation_score);
  const pool=candidates.slice(0,300);
  const poolKeys=new Set(pool.map(candidate=>candidate.key));
  for(const member of available){let covered=0;for(const candidate of candidates){if(candidate.members.some(item=>item.id===member.id)&&!poolKeys.has(candidate.key)){pool.push(candidate);poolKeys.add(candidate.key);if(++covered>=8)break;}}}
  if(requested>1){applyOpportunity(pool);applyCarryResourcePriority(pool);}pool.sort((a,b)=>b.allocation_score-a.allocation_score);
  const shortlist=pool.slice(0,240),shortlistKeys=new Set(shortlist.map(candidate=>candidate.key));for(const member of available){let covered=0;for(const candidate of pool){if(candidate.members.some(item=>item.id===member.id)&&!shortlistKeys.has(candidate.key)){shortlist.push(candidate);shortlistKeys.add(candidate.key);if(++covered>=16)break;}}}
  let allocations=[];
  if(String(team_count)==="all"){
    allocations=optimizeComplete(candidates,requested,8);
  }else{
    allocations=optimize(shortlist,requested,3);
    if(allocations.length){
      const originals=allocations;allocations=[originals[0]];
      const seen=new Set([allocations[0].map(team=>team.key).sort().join("||")]);
      for(const primaryTeam of allocations[0]){
        const forced=shortlist.find(candidate=>candidate.primary_carry_id===primaryTeam.primary_carry_id&&candidate.key!==primaryTeam.key);
        if(!forced)continue;
        const forcedCounts={};for(const member of forced.members)forcedCounts[member.usage_key]=(forcedCounts[member.usage_key]||0)+1;
        const compatible=shortlist.filter(candidate=>candidate.key!==forced.key&&candidate.members.every(member=>(forcedCounts[member.usage_key]||0)+1<=member._usage_limit));
        const remainder=requested>1?optimize(compatible,requested-1,1)[0]||[]:[];
        const variant=[forced,...remainder];if(variant.length!==requested)continue;
        const key=variant.map(team=>team.key).sort().join("||");
        if(!seen.has(key)){allocations.push(variant);seen.add(key);}
      }
      for(const allocation of originals.slice(1)){
        const key=allocation.map(team=>team.key).sort().join("||");
        if(!seen.has(key)){allocations.push(allocation);seen.add(key);}
      }
      allocations=allocations.slice(0,3);
    }
  }
  const configurations=allocations.map((allocation,index)=>{const teams=serialize(allocation,rules);return {id:index+1,label:`추천 구성 ${String.fromCharCode(65+index)}`,team_count:teams.length,total_score:round1(allocation.reduce((sum,team)=>sum+team.allocation_score,0)),combat_score:round1(teams.reduce((sum,team)=>sum+team.score,0)),teams};});
  const teams=configurations[0]?.teams||[];return {teams,configurations,maximum_team_count:teams.length,capacity_upper_bound:maximum,message:`검증된 완성 조합과 사용 횟수를 반영해 ${teams.length}개 파티의 서로 다른 배분안 ${configurations.length}가지를 계산했습니다.`,engine:"browser-hybrid-meta-v2",score_weights:SCORE_WEIGHTS,rules_version:rules.version,meta_patch:rules.meta_patch,meta_updated_at:rules.meta_updated_at,requested_team_count:team_count};
}
