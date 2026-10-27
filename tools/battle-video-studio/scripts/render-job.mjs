import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {bundle} from '@remotion/bundler';
import {renderMedia,renderStill,selectComposition} from '@remotion/renderer';
import {ROOT,slug} from './prepare-job.mjs';
import {ensureStarter} from './bootstrap.mjs';

await ensureStarter();

export async function browserPath() {
  for(const p of [process.env.BATTLE_VIDEO_BROWSER,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe']) {
    if(p && await fs.access(p).then(()=>true,()=>false)) return p;
  }
  return undefined;
}

export function renderOutputName({id,scale=1,stillFrame,frameRange,runId=randomUUID()}={}){
  return stillFrame!==undefined?`frame-${stillFrame}-${runId}.png`:`${slug(id)}${frameRange?`-frames-${frameRange[0]}-${frameRange[1]}`:''}${scale===1?'':'-preview'}-${runId}.mp4`;
}

export function compatibleVideoScale({width,height,scale=1}){
  const valid=s=>Number.isInteger(width*s)&&Number.isInteger(height*s)&&(width*s)%2===0&&(height*s)%2===0;
  if(valid(scale))return scale;
  const gcd=(a,b)=>b?gcd(b,a%b):a;
  const steps=gcd(width,height);let best;
  for(let n=1;n<=steps;n++){
    const candidate=n/steps;
    if(valid(candidate)&&(best===undefined||Math.abs(candidate-scale)<Math.abs(best-scale)))best=candidate;
  }
  if(best===undefined)throw Error('画幅无法按原比例生成偶数像素视频，请调整画幅尺寸。');
  return best;
}

export async function renderJob({id,scale=1,stillFrame,frameRange,outputDir,onProgress=()=>{}}={}) {
  if(!Number.isFinite(scale)||scale<=0||scale>1)throw Error('输出比例应大于 0 且不超过 1。');
  const active=JSON.parse(await fs.readFile(id?path.join(ROOT,'projects',slug(id),'compiled.json'):path.join(ROOT,'data','active-job.json'),'utf8'));
  const folder=outputDir?path.resolve(outputDir):path.join(ROOT,'outputs',active.id);
  await fs.mkdir(folder,{recursive:true});
  const statusFile=path.join(folder,'progress.json');
  const previous=await fs.readFile(statusFile,'utf8').then(JSON.parse).catch(()=>null);
  const lastSuccessfulOutput=previous?.stage==='done'?previous.output:previous?.lastSuccessfulOutput;
  const runId=randomUUID();
  const bundleFolder=path.resolve(ROOT,'.cache',`render-${runId}`);
  let writing=Promise.resolve();
  let renderInfo={};
  const update=state=>{
    const data={id:active.id,runId,lastSuccessfulOutput,updatedAt:new Date().toISOString(),...renderInfo,...state};
    writing=writing.then(async()=>{await fs.writeFile(statusFile,JSON.stringify(data));onProgress(data);});
    return writing;
  };
  try {
    await update({stage:'bundling',progress:0,message:'正在准备工程'});
    const serveUrl=await bundle({entryPoint:path.join(ROOT,'src','index.ts'),publicDir:path.join(ROOT,'public'),outDir:bundleFolder});
    const browserExecutable=await browserPath();
    const inputProps={job:active};
    const composition=await selectComposition({serveUrl,id:'BattleEdit',inputProps,browserExecutable});
    if(stillFrame!==undefined) {
      if(!Number.isInteger(stillFrame)||stillFrame<0||stillFrame>=composition.durationInFrames)throw Error('预览帧无效。');
      const outputLocation=path.join(folder,renderOutputName({id:active.id,stillFrame,runId}));
      await renderStill({serveUrl,composition,inputProps,output:outputLocation,frame:stillFrame,browserExecutable,scale});
      await update({stage:'done',progress:1,output:outputLocation,message:'预览帧已保存'});
      return outputLocation;
    }
    if(frameRange&&(!Array.isArray(frameRange)||frameRange.length!==2||!frameRange.every(Number.isInteger)||frameRange[0]<0||frameRange[1]<frameRange[0]||frameRange[1]>=composition.durationInFrames))throw Error('预览帧范围无效。');
    const videoScale=compatibleVideoScale({...composition,scale});
    renderInfo={requestedScale:scale,effectiveScale:videoScale,width:composition.width*videoScale,height:composition.height*videoScale};
    const outputLocation=path.join(folder,renderOutputName({id:active.id,frameRange,scale,runId}));
    let last=-1;
    await renderMedia({composition,serveUrl,inputProps,outputLocation,codec:'h264',audioCodec:'aac',pixelFormat:'yuv420p',
      browserExecutable,scale:videoScale,frameRange,concurrency:2,crf:18,timeoutInMilliseconds:60000,
      onProgress:p=>{
        const bucket=Math.floor(p.progress*100/5);
        if(bucket!==last){last=bucket;void update({stage:'rendering',progress:p.progress,renderedFrames:p.renderedFrames,totalFrames:frameRange?frameRange[1]-frameRange[0]+1:composition.durationInFrames,message:`正在渲染 ${Math.round(p.progress*100)}%`});}
      }});
    await update({stage:'done',progress:1,output:outputLocation,message:'成片已保存'});
    return outputLocation;
  } catch(error) {
    await update({stage:'error',progress:0,message:error.message});throw error;
  } finally {
    // Only this call's disposable bundle; never touch Studio or another run.
    if(path.dirname(bundleFolder)===path.resolve(ROOT,'.cache')&&path.basename(bundleFolder)===`render-${runId}`)await fs.rm(bundleFolder,{recursive:true,force:true}).catch(()=>{});
  }
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const get=name=>{const i=process.argv.indexOf(name);return i<0?undefined:process.argv[i+1];};
  const still=get('--still');
  try {
    await renderJob({id:get('--job'),scale:Number(get('--scale')||1),stillFrame:still===undefined?undefined:Number(still),frameRange:get('--range')?.split(':').map(Number),outputDir:get('--out'),onProgress:s=>console.log(JSON.stringify(s))});
  } catch(error){console.error(error.stack);process.exitCode=1;}
}
