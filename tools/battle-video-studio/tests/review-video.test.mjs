import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createReview,reviewWindows} from '../scripts/review-video.mjs';
const run=promisify(execFile);

test('all quick-slot frames and adjacent frames are covered, not sparse sampling',()=>{
 const windows=reviewWindows({fps:30,durationInFrames:60,scenes:[
  {type:'intro',from:0,duration:10},{type:'compare',from:10,duration:12},
  {type:'reveal',from:22,duration:16},{type:'verdict',from:38,duration:22}]});
 assert.deepEqual(windows.map(w=>[w.first,w.last]),[[8,23],[20,39]]);
 assert.throws(()=>reviewWindows({fps:30,durationInFrames:20,scenes:[{type:'reveal',from:18,duration:10}]}),/bounds/);
});

test('review extracts the one-frame foreign shot and refuses stale output reuse',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'battle-review-'));
 try{
  const final=path.join(root,'final.mp4'),output=path.join(root,'review');
  await run(process.env.FFMPEG_PATH||'ffmpeg',['-v','error','-f','lavfi','-i','color=blue:s=120x160:r=30:d=1',
   '-vf',"drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable='eq(n,10)'",'-c:v','libx264','-pix_fmt','yuv420p',final],{windowsHide:true,timeout:15000});
  const job={fps:30,durationInFrames:30,scenes:[{type:'reveal',from:9,duration:6,label:'<tag>',winner:'a'}]};
  const page=await createReview({job,final,output});
  const text=await fs.readFile(page,'utf8');
  const frames=(await fs.readdir(path.join(output,'scene-000'))).sort();
  assert.equal(frames.length,10);assert.ok(frames.includes('00000010.jpg'));
  assert.ok(text.includes('&lt;tag&gt;'));assert.ok(!text.includes('<tag>'));
  const red=await run('ffmpeg',['-v','error','-i',path.join(output,'scene-000','00000010.jpg'),'-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],{encoding:null,windowsHide:true});
  const blue=await run('ffmpeg',['-v','error','-i',path.join(output,'scene-000','00000011.jpg'),'-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],{encoding:null,windowsHide:true});
  assert.ok(red.stdout[0]>200&&red.stdout[2]<60);assert.ok(blue.stdout[2]>200&&blue.stdout[0]<60);
  await assert.rejects(createReview({job,final,output}),/EEXIST/);
 }finally{
  const parent=await fs.realpath(os.tmpdir());
  const actual=await fs.realpath(root);
  if(path.dirname(actual)===parent&&path.basename(actual).startsWith('battle-review-'))await fs.rm(actual,{recursive:true,force:true});
 }
});
