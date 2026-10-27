// This module consumes host-assigned semantics. It does not inspect or grade pixels.
const ranks={S:4,A:3,B:2,C:1,unrated:0};
const tier=c=>ranks[c.qualityTier||'unrated']??0;
const eligible=(c,role)=>c.qualityTier!=='exclude'&&c.cropUsable!==false&&(c.role===role||c.role==='any');
const source=c=>String(c.sourceId||c.src).replaceAll('\\','/').toLowerCase();
const start=c=>c.sourceIn??c.trimIn;
const end=c=>c.sourceOut??c.trimOut;
const motion=c=>c.motion||(c.kind==='image'?'still':'native');
const exciting=c=>c.excitement?c.excitement==='exciting':tier(c)>=3;
const compare=(a,b)=>tier(b)-tier(a)||(a.role==='any')-(b.role==='any');
const displayFrames=(c,fps,speed=c.speed)=>c.kind==='image'?Math.floor((c.displayDuration??4)*fps):Math.floor((c.trimOut-c.trimIn)*fps/speed+1e-6);
const range=c=>({sourceId:source(c),start:start(c),end:end(c),still:c.kind==='image'});
const overlaps=(a,b)=>a.sourceId===b.sourceId&&(a.still||b.still||a.start<b.end-1e-7&&b.start<a.end-1e-7);
const reserve=(c,used)=>used.push(range(c));

function subclip(c,offsetSeconds,lengthSeconds,speed=c.speed){
 const ratio=(end(c)-start(c))/(c.trimOut-c.trimIn);
 return {...c,trimIn:c.trimIn+offsetSeconds,trimOut:c.trimIn+offsetSeconds+lengthSeconds,speed,
  sourceId:c.sourceId||c.src,sourceIn:start(c)+offsetSeconds*ratio,sourceOut:start(c)+(offsetSeconds+lengthSeconds)*ratio};
}

// Allocate only still-unused intervals from the same original source, including
// when two candidates have different local filenames or trim coordinates.
function freeClips(clips,used,fps){
 return clips.flatMap(c=>{
  if(c.kind==='image')return used.some(u=>overlaps(range(c),u))?[]:[c];
  let spans=[[start(c),end(c)]];
  for(const u of used.filter(u=>u.sourceId===source(c))){
   spans=spans.flatMap(([a,b])=>u.still?[]:u.end<=a||u.start>=b?[[a,b]]:[[a,Math.min(b,u.start)],[Math.max(a,u.end),b]].filter(([x,y])=>y>x));
  }
  const ratio=(c.trimOut-c.trimIn)/(end(c)-start(c));
  return spans.map(([a,b])=>subclip(c,(a-start(c))*ratio,(b-a)*ratio)).filter(v=>displayFrames(v,fps,.5)>=1);
 });
}

export class MediaPlanError extends Error{
 constructor(gaps,notes=[]){
  super(gaps.map(g=>`${g.character} / ${g.role}：${g.action}`).join('\n'));
  this.name='MediaPlanError';this.code='MEDIA_GAPS';this.gaps=gaps;this.notes=notes;
 }
}

export function normalizeClipInput(raw,meta,{fps=30,label='素材'}={}){
 const number=(name,value,fallback)=>{
  const n=Number(value===undefined||value===null||value===''?fallback:value);
  if(!Number.isFinite(n))throw Error(`${label} 的 ${name} 必须是有限数值。`);return n;
 };
 const kind=raw.kind||'video';
 if(raw.sourceId!==undefined&&(typeof raw.sourceId!=='string'||!raw.sourceId.trim()))throw Error(`${label} 的 sourceId 必须是非空原片标识。`);
 const duration=kind==='image'?1:meta.duration;
 const requestedIn=number('trimIn',raw.trimIn,0),requestedOut=number('trimOut',raw.trimOut,duration);
 const speed=number('speed',raw.speed,1);
 if(speed<.5)throw Error(`${label} 的 speed 最低为 0.5；请补充片段，不能靠更低速度凑长。`);
 if(requestedIn<0||requestedOut<=requestedIn||requestedOut>duration+.001)throw Error(`${label} 的有效区间应在 0—${duration.toFixed(3)} 秒内，且 trimOut 大于 trimIn。`);
 const trimIn=kind==='image'?requestedIn:Math.ceil(requestedIn*fps-1e-6)/fps;
 const trimOut=kind==='image'?requestedOut:Math.floor(Math.min(requestedOut,duration)*fps+1e-6)/fps;
 if(trimOut<=trimIn)throw Error(`${label} 的区间不足一个 ${fps}fps 展示帧，请重新划入出点。`);
 const sourceIn=number('sourceIn',raw.sourceIn,requestedIn),sourceOut=number('sourceOut',raw.sourceOut,sourceIn+requestedOut-requestedIn);
 if(sourceIn<0||sourceOut<=sourceIn)throw Error(`${label} 的 sourceIn/sourceOut 需要有效的原片区间。`);
 const ratio=(sourceOut-sourceIn)/(requestedOut-requestedIn);
 const displayDuration=raw.displayDuration===undefined?undefined:number('displayDuration',raw.displayDuration,4);
 if(displayDuration!==undefined&&displayDuration<=0)throw Error(`${label} 的 displayDuration 必须大于 0。`);
 const focalX=number('focalX',raw.focalX,50),focalY=number('focalY',raw.focalY,45);
 if([focalX,focalY].some(n=>n<0||n>100))throw Error(`${label} 的构图焦点应在 0—100。`);
 if(raw.role&&!['intro','plate','highlight','finish','any'].includes(raw.role))throw Error(`${label} 的 role 无效；请选择 intro/plate/highlight/finish/any。`);
 for(const [key,values] of [['excitement',['exciting','ordinary']],['motion',['native','animated','still']]])if(raw[key]!==undefined&&!values.includes(raw[key]))throw Error(`${label} 的 ${key} 无效。`);
 for(const key of ['continuous','cropUsable','allowSlowdown'])if(raw[key]!==undefined&&typeof raw[key]!=='boolean')throw Error(`${label} 的 ${key} 必须为 true 或 false。`);
 return {trimIn,trimOut,speed,focalX,focalY,sourceIn:sourceIn+(trimIn-requestedIn)*ratio,sourceOut:sourceIn+(trimOut-requestedIn)*ratio,displayDuration};
}

// A resumed slow clip can begin halfway through a source frame. Round down
// inside the already inward-aligned candidate so its last sample never leaks
// into the next unapproved shot; keep enough trim duration for that sample.
export function videoFrameWindow(clip,fps){
 const before=Math.floor(clip.trimIn*fps+1e-6);
 return {before,length:Math.max(1,Math.ceil(clip.trimOut*fps-before-1e-6))};
}

export function sceneMediaSpec(job,scene){
 const nine=job.renderer==='nine-templates';
 if(nine&&scene.type==='outro'&&['V02','V03','V04'].includes(job.templateId))return {role:'none',sides:[],split:false};
 const split=scene.type==='compare'||scene.type==='intro'&&(!nine||scene.layout!=='full')||['outro','tail'].includes(scene.type)||scene.winner==='tie'&&scene.type!=='intro';
 const role=scene.type==='intro'?'intro':split?'plate':scene.type==='reveal'?'highlight':'finish';
 return {role,split,sides:split?['a','b']:[scene.type==='intro'?(scene.subject||'a'):scene.winner==='b'?'b':'a']};
}

function sequence(clips,frames,fps,slow=false){
 const used=[],result=[];let left=frames;
 const available=()=>freeClips(clips,used,fps).sort(compare);
 // One fitting continuous shot wins within an equally exciting category.
 const fitting=available().find(c=>c.continuous!==false&&displayFrames(c,fps,slow&&c.allowSlowdown!==false?.5:c.speed)>=left);
 if(fitting)clips=[fitting];
 for(const original of clips){
  for(const c of freeClips([original],used,fps)){
   if(left<=0)break;
   const minimum=slow&&c.allowSlowdown!==false?.5:c.speed;
   const capacity=displayFrames(c,fps,minimum);
   const take=Math.min(left,capacity);if(take<1)continue;
   const speed=c.kind==='image'?1:slow?Math.min(c.speed,Math.max(minimum,(c.trimOut-c.trimIn)*fps/take)):c.speed;
   const selected=c.kind==='image'?c:subclip(c,0,Math.min(c.trimOut-c.trimIn,take*speed/fps),speed);
   result.push({from:frames-left,duration:take,clip:selected,loop:false});
   reserve(selected,used);left-=take;
  }
  if(left<=0)break;
 }
 return {segments:result,remaining:left};
}

function inBand(clips,frames,fps){
 const native=clips.filter(c=>motion(c)==='native');
 const good=native.filter(exciting),ordinary=native.filter(c=>!exciting(c));
 const original=good.filter(c=>c.speed>=1);
 const single=original.filter(c=>c.continuous!==false&&displayFrames(c,fps)>=frames).sort(compare)[0];
 if(single)return sequence([single],frames,fps);
 const short=sequence(original,frames,fps);if(!short.remaining)return short;
 const slower=sequence(good,frames,fps,true);if(!slower.remaining)return slower;
 // Partial higher-priority footage is retained when the rest needs fallback.
 const chosen=[];const used=[];let left=frames;
 for(const [pool,slow] of [[good,true],[ordinary,false],[clips.filter(c=>motion(c)==='animated'),false],[clips.filter(c=>motion(c)==='still'),false]]){
  const result=sequence(freeClips(pool,used,fps).sort(compare),left,fps,slow);
  for(const s of result.segments){chosen.push({...s,from:frames-left+s.from});reserve(s.clip,used);}
  left=result.remaining;if(!left)break;
 }
 return {segments:chosen,remaining:left};
}

function longPlan(clips,frames,fps){
 const result=[];const used=[];let left=frames;
 // High-quality stills remain ahead of poor gameplay. The six-step motion
 // preference applies inside the same quality band; no file-type trump card.
 for(const band of [[4,3],[2],[1],[0]]){
  const candidates=freeClips(clips.filter(c=>band.includes(tier(c))),used,fps).sort(compare);
  const selected=inBand(candidates,left,fps);
  for(const s of selected.segments){result.push({...s,from:frames-left+s.from});reserve(s.clip,used);}
  left=selected.remaining;if(!left)break;
 }
 return {segments:result,remaining:left};
}

function slicePlan(segments,from,duration,fps){
 return segments.flatMap(s=>{
  const a=Math.max(from,s.from),b=Math.min(from+duration,s.from+s.duration);if(b<=a)return [];
  const offset=(a-s.from)*s.clip.speed/fps,length=(b-a)*s.clip.speed/fps;
  return [{...s,from:a-from,duration:b-a,clip:s.clip.kind==='image'?s.clip:subclip(s.clip,offset,length)}];
 });
}

export function planMedia(input){
 const job=structuredClone(input),fps=job.fps,used=[],gaps=[],notes=[];
 const requirements={};
 for(const [i,s] of job.scenes.entries()){
  s.media={};const spec=sceneMediaSpec(job,s);
  for(const side of spec.sides){const key=`${side}:${spec.role}`;(requirements[key]??=[]).push({index:i,duration:s.duration});}
 }
 // Reserve the roles with fewer alternatives first, so a flexible intro does
 // not consume the sole valid finish. At equal flexibility prefer short roles.
 const roles=['plate','highlight','intro','finish'];
 const groups=roles.flatMap(role=>['a','b'].filter(side=>requirements[`${side}:${role}`]?.length).map(side=>({role,side,
  options:new Set(job.characters[side].clips.filter(c=>eligible(c,role)).map(c=>JSON.stringify(range(c)))).size
 }))).sort((a,b)=>a.options-b.options||roles.indexOf(a.role)-roles.indexOf(b.role));
 for(const {role,side} of groups){
  const windows=requirements[`${side}:${role}`];if(!windows?.length)continue;
  const character=job.characters[side];
  const pool=freeClips(character.clips.filter(c=>eligible(c,role)),used,fps).sort(compare);
  const total=windows.reduce((n,w)=>n+w.duration,0);
  if(!pool.length){gaps.push({side,character:character.name,role,requiredSeconds:total/fps,missingSeconds:total/fps,action:`补充已看过、适合 ${role} 且未与其他位置重叠的素材；可标 role: "${role}"（或明确适配的 any），再设置有效入出点。`});continue;}
  if(role==='plate'||role==='highlight'){
   const floor=role==='highlight'?Math.min(3,tier(pool[0])):tier(pool[0]);
   const chosen=[];const own=[];
   const maximum=Math.max(...windows.map(w=>w.duration));
   for(const c of pool.filter(c=>tier(c)>=floor)){
    if(own.some(u=>overlaps(range(c),u)))continue;
    const selected=c.kind==='image'?c:subclip(c,0,Math.min(c.trimOut-c.trimIn,maximum*c.speed/fps));
    chosen.push(selected);reserve(selected,own);reserve(selected,used);
    if(role==='plate')break;
   }
   if(role==='highlight'&&chosen.length<2)notes.push(`${character.name} 只有一段互不重叠的优选 highlight；本次按既有规则重复它。要交替请补一段独立的 S/A 高光。`);
   for(const [ordinal,w] of windows.entries()){
    const c=chosen[role==='plate'?0:ordinal%chosen.length];
    job.scenes[w.index].media[side]=[{from:0,duration:w.duration,clip:c,loop:c.kind!=='image'&&w.duration>displayFrames(c,fps)}];
   }
  }else{
   const planned=longPlan(pool,total,fps);
   if(planned.remaining){const missing=planned.remaining/fps;gaps.push({side,character:character.name,role,requiredSeconds:total/fps,availableSeconds:(total-planned.remaining)/fps,missingSeconds:missing,action:`仍缺 ${missing.toFixed(3)} 秒展示。补充不同源区间的精彩 ${role} 视频/动效/图片；当前允许的慢放已计入（最低 0.5），图片可明确 displayDuration。不循环已有长展示。`});continue;}
   for(const s of planned.segments)reserve(s.clip,used);
   let cursor=0;for(const w of windows){job.scenes[w.index].media[side]=slicePlan(planned.segments,cursor,w.duration,fps);cursor+=w.duration;}
   if(planned.segments.some(s=>s.clip.speed<1))notes.push(`${character.name} / ${role} 已按时长规划慢放，最低 ${Math.min(...planned.segments.map(s=>s.clip.speed)).toFixed(3)} 倍；音乐时序未改变。`);
  }
 }
 if(gaps.length)throw new MediaPlanError(gaps,notes);
 job.mediaPlanning={version:1,notes};return job;
}
