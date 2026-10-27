import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {selectProjectTemplate} from './select-template.mjs';
import {normalizeClipInput,planMedia} from '../src/media-plan.mjs';

export const ROOT=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const run=promisify(execFile);
const readJson=async p=>JSON.parse((await fs.readFile(p,'utf8')).replace(/^\uFEFF/,''));
export const slug=value=>String(value).replace(/[^\p{L}\p{N}._-]/gu,'-').replace(/^\.+/,'').slice(0,90)||'battle-edit';
const exists=async p=>fs.access(p).then(()=>true,()=>false);
const publicPath=relative=>path.join(ROOT,'public',relative);

async function probe(filename,cache) {
  const stat=await fs.stat(filename);
  const old=cache[filename];
  if(old?.version===2 && old.size===stat.size && old.mtimeMs===stat.mtimeMs) return old.probe;
  const {stdout}=await run(process.env.FFPROBE_PATH||'ffprobe',['-v','error','-show_streams','-show_format','-of','json',filename],{timeout:20000,maxBuffer:1024*1024,windowsHide:true});
  const metadata=JSON.parse(stdout);
  const stream=metadata.streams.find(s=>s.codec_type==='video');
  const result={duration:Number(stream?.duration||metadata.format.duration||0),width:stream?.width,height:stream?.height};
  cache[filename]={version:2,size:stat.size,mtimeMs:stat.mtimeMs,probe:result};
  return result;
}

async function stageAsset(filename,jobId,index,baseDir) {
  const source=await fs.realpath(path.isAbsolute(filename)?filename:path.resolve(baseDir,filename));
  if(source.startsWith(path.join(ROOT,'public')+path.sep)) return {source,originalSource:source,src:path.relative(path.join(ROOT,'public'),source).replaceAll('\\','/')};
  const relative=`projects/${jobId}/${index}-${slug(path.basename(source))}`;
  const target=publicPath(relative);
  await fs.mkdir(path.dirname(target),{recursive:true});
  const st=await fs.stat(source),dest=await fs.stat(target).catch(()=>null);
  if(!dest || dest.size!==st.size || Math.abs(dest.mtimeMs-st.mtimeMs)>2) {
    await fs.copyFile(source,target);
    await fs.utimes(target,st.atime,st.mtime);
  }
  return {source:target,originalSource:source,src:relative};
}

export async function prepareJob(input,{baseDir=ROOT,onMessage=()=>{},activate=true}={}) {
  const job=structuredClone(input);
  const demonstration=['reference-demo','media-demo'].includes(job.mode);
  if(['story','writing','writing-demo'].includes(job.mode)||job.sourceKind==='story')throw Error('故事胜局不能直接作为正式属性视频结论；先复用独立评级并完成普通PK比较。');
  const difficultyNames={no:['无难度','No Diff'],low:['低难度','Low Diff'],mid:['中难度','Mid Diff'],high:['高难度','High Diff'],extreme:['极高难度','Extreme Diff']};
  const difficulty=job.verdict?.difficulty;
  if(!demonstration&&(!['a','b'].includes(job.verdict?.winner)||!difficultyNames[difficulty]))throw Error('正式胜负视频需要上游明确总胜者及五档获胜难度；剪辑器不按赢项数推算。');
  const id=slug(job.id||`battle-${Date.now()}`);
  const previousProject=await readJson(path.join(ROOT,'projects',id,'compiled.json')).catch(()=>null);
  const selected=await selectProjectTemplate(job,previousProject);
  job.templateId=selected.templateId;
  job.templateSelection=selected.templateSelection;
  const defaults=selected.defaults;
  const template=await readJson(path.join(ROOT,'templates',`${slug(job.templateId)}.json`));
  const preset=(await readJson(path.join(ROOT,'data/video-presets.json')))[template.id]||{introShots:[],ending:{brandAt:template.stages.at(-1)[0]}};
  if(!job.characters?.a?.name || !job.characters?.b?.name) throw Error('请填写双方名字，并添加双方素材。');
  const comparisons=job.comparisons||job.ratingComparison?.dimensions||[];
  if(comparisons.length!==template.comparison_slot_count) throw Error(`音乐模板 ${template.id} 有 ${template.comparison_slot_count} 个比较展示位，当前提供 ${comparisons.length} 项。请选择匹配模板或明确调整展示项目；完整评级无需删减。`);
  if(!['a','b','tie'].includes(job.verdict?.winner)) throw Error('请从既有PK结果填写胜者 a、b 或 tie；剪辑器不判胜负。');
  const cachePath=path.join(ROOT,'data','media-cache.local.json');
  const cache=await readJson(cachePath).catch(()=>({}));
  const frameSize=job.output||{};
  const fps=Number(frameSize.fps||30);
  const width=Number(frameSize.width||template.frame_size[0]);
  const height=Number(frameSize.height||template.frame_size[1]);
  if(![fps,width,height].every(Number.isFinite)||fps<1||fps>120||width<240||height<240||width%2||height%2) throw Error('请使用有效帧率和偶数尺寸（例如1080×1440，30fps）。');
  const characters={};
  for(const side of ['a','b']) {
    const c=job.characters[side];
    if(!c.clips?.length) throw Error(`${c.name} 还没有素材。`);
    characters[side]={name:c.name,version:c.version||'',tier:c.tier||'',clips:[]};
    for(const [i,raw] of c.clips.entries()) {
      if(raw.qualityTier==='exclude'||raw.cropUsable===false)continue;
      onMessage(`准备 ${c.name} 的素材 ${i+1}/${c.clips.length}`);
      const staged=await stageAsset(raw.path||raw.src,id,`${side}-${i}`,baseDir);
      const kind=/\.(png|jpe?g|webp|avif|bmp)$/i.test(staged.source)?'image':'video';
      const meta=await probe(staged.source,cache);
      if(kind==='video' && !(meta.duration>0)) throw Error(`无法读取视频时长：${staged.source}`);
      const values=normalizeClipInput({...raw,kind},meta,{fps,label:`${c.name} / ${i+1}`});
      const sourceId=raw.sourceId||staged.originalSource;
      characters[side].clips.push({id:raw.id||`${side}-${i}`,src:staged.src,kind,duration:meta.duration,width:meta.width||1080,height:meta.height||1440,...values,
        sourceId,role:raw.role||'any',excitement:raw.excitement,motion:raw.motion,continuous:raw.continuous,cropUsable:raw.cropUsable,allowSlowdown:raw.allowSlowdown,
        qualityTier:['S','A','B','C'].includes(raw.qualityTier)?raw.qualityTier:'unrated',qualityReason:raw.qualityReason||''});
      raw.path=staged.source;
      raw.sourceId=sourceId;
    }
    if(!characters[side].clips.length)throw Error(`${c.name}没有未排除的素材，请继续选材。`);
  }
  const musicSource=job.audio?.path?await stageAsset(job.audio.path,id,'audio',baseDir):{source:publicPath(template.audio_file),src:template.audio_file};
  await fs.access(musicSource.source).catch(()=>{throw Error(`Missing ${template.id} audio. Import your licensed matching edit with: node scripts/import-music.mjs --template ${template.id} --file your-audio.wav ; or set audio.path in the job.`);});
  const musicMeta=await probe(musicSource.source,cache);
  if(musicMeta.duration && musicMeta.duration+0.15<template.duration_s) throw Error('音乐长度短于此时间表，请选择对应音轨或重标模板。');
  const durationInFrames=Math.ceil(template.duration_s*fps);
  const scenes=[];
  const add=(type,start,end,label='',winner='tie',slotIndex=-1,extra={})=>{
    const from=Math.max(0,Math.round(start*fps));
    const to=Math.min(durationInFrames,Math.round(end*fps));
    if(to>from) scenes.push({type,from,duration:to-from,label,winner,slotIndex,...extra});
  };
  const compareSlots=template.slots.filter(s=>s.original_role!=='verdict');
  const verdictSlot=template.slots.find(s=>s.original_role==='verdict');
  const compareStart=compareSlots[0].label_cut_s;
  // Long intros use several source clips rather than resetting the same frame every beat.
  if(preset.introShots.length&&!job.introCuts){
    for(const [i,shot] of preset.introShots.entries())add('intro',shot.start,shot.end,'','tie',i,{layout:'full',subject:shot.side});
  }else{
    const introCuts=[0,...(job.introCuts||[]).filter(t=>t>0&&t<compareStart),compareStart].sort((a,b)=>a-b);
    for(let i=0;i<introCuts.length-1;i++) add('intro',introCuts[i],introCuts[i+1],'VS','tie',i,{layout:'split'});
  }
  for(const [i,slot] of compareSlots.entries()) {
    const entry=comparisons[i];
    const winner=entry.winner;
    if(!['a','b','tie'].includes(winner)) throw Error(`第${i+1}项的揭晓者必须是a、b或tie。`);
    const next=compareSlots[i+1]?.label_cut_s??verdictSlot?.label_cut_s??template.stages.at(-1)[0];
    const label=entry.label||slot.original_label;
    add('compare',slot.label_cut_s,slot.reveal_cut_s,label,winner,i,{valueA:entry.valueA||'',valueB:entry.valueB||''});
    add('reveal',slot.reveal_cut_s,next,label,winner,i);
  }
  const outroStart=template.stages.at(-1)[0];
  const finalStart=verdictSlot?.label_cut_s??outroStart;
  const finalReveal=verdictSlot?.reveal_cut_s??finalStart;
  const finalEnd=verdictSlot?(preset.ending.brandAt??template.duration_s):template.duration_s;
  if(finalReveal>finalStart) add('compare',finalStart,finalReveal,job.verdict.label||'胜者',job.verdict.winner,compareSlots.length);
  if(verdictSlot){
    add('verdict',finalReveal,finalEnd,job.verdict.label||'胜者',job.verdict.winner,compareSlots.length,{mediaFrom:Math.round(finalReveal*fps)});
    if(finalEnd<template.duration_s)add('outro',finalEnd,template.duration_s,job.style?.watermark||defaults.watermark,job.verdict.winner,compareSlots.length+1);
  }else{
    add('outro',finalStart,template.duration_s,job.style?.watermark||defaults.watermark,job.verdict.winner,compareSlots.length,{showVerdict:true});
  }
  const compiled=planMedia({id,title:job.title||`${characters.a.name} vs ${characters.b.name}`,mode:job.mode||'production',fps,width,height,durationInFrames,
    templateId:template.id,renderer:job.renderer||(previousProject?(previousProject.renderer||'legacy'):selected.renderer),templateSelection:job.templateSelection,music:musicSource.src,musicVolume:Number(job.audio?.volume??.9),characters,scenes,
    verdict:{winner:job.verdict.winner,label:job.verdict.label||'胜者',subtitle:job.verdict.subtitle||'',difficulty,
      difficultyText:job.verdict.difficultyText||(difficultyNames[difficulty]?(String(job.language||'zh').startsWith('en')?`Difficulty: ${difficultyNames[difficulty][1]}`:`难度：${difficultyNames[difficulty][0]}`):'难度：未评定（演示）'),
      difficultyReason:job.verdict.difficultyReason||''},
    style:{accent:job.style?.accent||'#edff57',accentB:job.style?.accentB||'#ff5478',intensity:Number(job.style?.intensity??.65),
      watermark:job.style?.watermark??defaults.watermark,showValues:Boolean(job.style?.showValues),textScale:Number(job.style?.textScale??defaults.textScale),vsPresentation:job.style?.vsPresentation||defaults.vsPresentation,
      vsVariant:['silver','ink','prism','comic'].includes(job.style?.vsVariant)?job.style.vsVariant:defaults.vsVariant}});
  const folder=path.join(ROOT,'projects',id);
  await fs.mkdir(folder,{recursive:true});
  await fs.mkdir(path.join(ROOT,'data'),{recursive:true});
  await fs.writeFile(path.join(folder,'job.json'),JSON.stringify({...job,id},null,2));
  await fs.writeFile(path.join(folder,'compiled.json'),JSON.stringify(compiled,null,2));
  if(activate)await fs.writeFile(path.join(ROOT,'data','active-job.json'),JSON.stringify(compiled,null,2));
  await fs.writeFile(cachePath,JSON.stringify(cache));
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  const table=[['类型','开始秒','结束秒','展示项','揭晓者'],...scenes.map(s=>[s.type,(s.from/fps).toFixed(3),((s.from+s.duration)/fps).toFixed(3),s.label,s.winner==='tie'?'双方':characters[s.winner].name])];
  await fs.writeFile(path.join(folder,'剪辑时间表.csv'),'\uFEFF'+table.map(r=>r.map(quote).join(',')).join('\r\n'));
  onMessage(`工程已准备：${id} / ${comparisons.length}个展示位 / ${(durationInFrames/fps).toFixed(2)}秒`);
  return {id,folder,compiled,projectFile:path.join(folder,'job.json')};
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const filename=process.argv[2];
  const jsonOutput=process.argv.includes('--json');
  if(!filename) {console.error('用法：npm run prepare-job -- 任务.json');process.exitCode=1;}
  else try {
    const result=await prepareJob(await readJson(filename),{baseDir:path.dirname(path.resolve(filename)),
      activate:!process.argv.includes('--no-activate'),onMessage:jsonOutput?()=>{}:console.log});
    if(jsonOutput)console.log(JSON.stringify({id:result.id,projectFile:result.projectFile,
      templateId:result.compiled.templateId,duration:result.compiled.durationInFrames/result.compiled.fps,
      mediaPlanning:result.compiled.mediaPlanning}));
  }
  catch(error) {
    if(jsonOutput)console.log(JSON.stringify({status:'error',error:error.message,
      ...(error.code?{code:error.code}:{}),...(error.gaps?{gaps:error.gaps}:{}),...(error.notes?{notes:error.notes}:{})}));
    else console.error(error.message);
    process.exitCode=1;
  }
}
