import fs from 'node:fs/promises';
import path from 'node:path';
import {randomInt} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export async function selectTemplate(requested){
 const defaults=JSON.parse(await fs.readFile(path.join(root,'data/video-defaults.json'),'utf8'));
 const explicit=Boolean(requested&&requested!=='random');
 if(explicit&&!/^[A-Za-z0-9_-]+$/.test(requested))throw Error('模板ID含无效字符。');
 const id=explicit?requested:defaults.presetPool[randomInt(defaults.presetPool.length)];
 const timing=JSON.parse(await fs.readFile(path.join(root,'templates',`${id}.json`),'utf8'));
 return {templateId:id,templateSelection:{mode:explicit?'explicit':'random',pool:defaults.presetPool,selectedAt:new Date().toISOString()},
  renderer:defaults.presetPool.includes(id)?defaults.renderer:'legacy',comparisonSlots:timing.comparison_slot_count,durationSeconds:timing.duration_s,timingFile:`templates/${id}.json`,audioFile:timing.audio_file,
  stages:timing.stages.map(s=>({start:s[0],end:s[1],role:s[2]})),defaults};
}
// Omission means “keep this project”. Only a supplied different ID (or random)
// asks for a new selection. Preserve the original draw's timestamp and mode.
export async function selectProjectTemplate(job,previous){
 const requested=job.templateId;
 const inherited=!requested&&previous?.templateId;
 const selected=await selectTemplate(inherited||requested);
 const same=previous?.templateId===selected.templateId&&requested!=='random';
 selected.templateSelection=same
  ?(previous.templateSelection||job.templateSelection||selected.templateSelection)
  :(job.templateSelection&&(!previous||!requested)?job.templateSelection:selected.templateSelection);
 return selected;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const at=process.argv.indexOf('--template');
 console.log(JSON.stringify(await selectTemplate(at<0?undefined:process.argv[at+1]),null,2));
}
