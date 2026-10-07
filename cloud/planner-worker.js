import {recommendInBrowser} from "./cloud-planner.js?v=20261007-support-allocation";

self.onmessage=event=>{
  const {id,payload}=event.data||{};
  try{
    self.postMessage({id,type:"progress",message:"보유 캐릭터의 유효 조합을 비교하고 있어요…"});
    const result=recommendInBrowser(payload||{});
    self.postMessage({id,type:"result",result});
  }catch(error){
    self.postMessage({id,type:"error",message:error?.message||String(error)});
  }
};
