// A viewing aid, not a visual classifier, acceptance gate or rating checker.
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
const run=promisify(execFile);
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const html=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');

export function reviewWindows(job,pad=2){
 if(!Number.isFinite(job.fps)||job.fps<=0||!Number.isInteger(job.durationInFrames)||!Array.isArray(job.scenes))throw Error('Invalid compiled timeline.');
 return job.scenes.flatMap((s,i)=>{
  if(!['compare','reveal'].includes(s.type))return [];
  if(!Number.isInteger(s.from)||!Number.isInteger(s.duration)||s.from<0||s.duration<1||s.from+s.duration>job.durationInFrames)throw Error('Invalid scene bounds.');
  return [{index:i,type:s.type,label:s.label||s.type,winner:s.winner,
   first:Math.max(0,s.from-pad),last:Math.min(job.durationInFrames-1,s.from+s.duration-1+pad),
   from:s.from,duration:s.duration}];
 });
}

export async function createReview({job,final,output,ffmpeg=process.env.FFMPEG_PATH||'ffmpeg'}){
 const destination=path.resolve(output),media=path.resolve(final);
 await fs.access(media);
 if(media===destination||media.startsWith(destination+path.sep))throw Error('Review output must not contain or replace the source video.');
 await fs.mkdir(destination,{recursive:false}); // Refuse an old directory instead of mixing revisions.
 const windows=reviewWindows(job),sections=[];
 for(const w of windows){
  const folder=`scene-${String(w.index).padStart(3,'0')}`;
  await fs.mkdir(path.join(destination,folder));
  // Decode the actual final file by frame number. No -ss keyframe shortcut or
  // sparse sampling: keep every frame, including the joins on both sides.
  await run(ffmpeg,['-v','error','-i',media,'-an','-vf',`select=between(n\\,${w.first}\\,${w.last}),scale=540:-2`,
   '-fps_mode','passthrough','-start_number',String(w.first),path.join(destination,folder,'%08d.jpg')],
   {windowsHide:true,timeout:60000,maxBuffer:1024*1024});
  const files=(await fs.readdir(path.join(destination,folder))).filter(f=>f.endsWith('.jpg')).sort();
  if(files.length!==w.last-w.first+1)throw Error(`Scene ${w.index}: final video does not cover the compiled frame window. Review remains incomplete.`);
  sections.push(`<section><h2>${w.index}: ${html(w.type)} / ${html(w.label)}</h2><p>${(w.from/job.fps).toFixed(3)}–${((w.from+w.duration)/job.fps).toFixed(3)} s; ${html(w.winner||'')} (includes adjacent frames)</p><div class="frames">${files.map(f=>{
   const n=Number(f.slice(0,-4)),url=`${folder}/${f}`,adjacent=n<w.from||n>=w.from+w.duration;
   return `<figure class="${adjacent?'adjacent':''}"><a href="${url}" target="_blank"><img loading="lazy" src="${url}"></a><figcaption>frame ${n} · ${(n/job.fps).toFixed(3)}s${adjacent?' · adjacent':''}</figcaption></figure>`;
  }).join('')}</div></section>`);
 }
 const page=`<!doctype html><meta charset="utf-8"><title>Battle Scaling — Frame Review</title><style>body{background:#17191e;color:#f2f2f2;font:16px system-ui;margin:24px}a{color:inherit}.frames{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:360px}img{width:100%;height:auto}figcaption{padding:6px}.adjacent{outline:2px solid #ffa748}section{border-top:1px solid #555;padding:12px 0}p{max-width:1000px}</style><h1>Battle Scaling — Frame Review</h1><p>Every comparison/reveal frame from the exported video, with two adjacent frames on each side. Click to enlarge. This page does not detect faces, judge excitement, or certify quality. Watch the full video at normal speed as well.</p>${sections.join('')}`;
 const target=path.join(destination,'index.html');
 await fs.writeFile(target,page);
 return target;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const get=name=>{const i=process.argv.indexOf(name);return i<0?undefined:process.argv[i+1];};
 try{
  const id=get('--job'),final=get('--final'),output=get('--out');
  if(!id||!final||!output||!/^[-\w]+$/.test(id))throw Error('Usage: node scripts/review-video.mjs --job project-id --final final.mp4 --out new-directory');
  const job=JSON.parse(await fs.readFile(path.join(ROOT,'projects',id,'compiled.json'),'utf8'));
  console.log(await createReview({job,final,output}));
 }catch(error){console.error(error.message);process.exitCode=1;}
}
