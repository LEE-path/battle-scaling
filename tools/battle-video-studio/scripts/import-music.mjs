import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),run=promisify(execFile);
const get=flag=>{const i=process.argv.indexOf(flag);return i<0?undefined:process.argv[i+1];};
try{
 const id=get('--template'),source=get('--file');
 if(!/^V0[1-9]$/.test(id||'')||!source)throw Error('Usage: node scripts/import-music.mjs --template V05 --file "your-audio.wav" [--replace]');
 const template=JSON.parse(await fs.readFile(path.join(root,'templates',`${id}.json`),'utf8'));
 const {stdout}=await run(process.env.FFPROBE_PATH||'ffprobe',['-v','error','-show_format','-of','json',path.resolve(source)],{windowsHide:true});
 const duration=Number(JSON.parse(stdout).format?.duration);
 if(!Number.isFinite(duration)||duration+.15<template.duration_s)throw Error(`Audio needs at least ${template.duration_s.toFixed(3)} seconds. Match the exact preset edit; duration alone does not verify musical identity.`);
 const target=path.join(root,'public',template.audio_file);await fs.mkdir(path.dirname(target),{recursive:true});
 if(!process.argv.includes('--replace')&&await fs.access(target).then(()=>true,()=>false))throw Error('This preset already has audio. Use --replace only when you intend to replace it.');
 const temporary=path.join(path.dirname(target),`.import-${randomUUID()}.m4a`);
 await run(process.env.FFMPEG_PATH||'ffmpeg',['-v','error','-i',path.resolve(source),'-vn','-c:a','aac','-b:a','256k','-t',String(template.duration_s),temporary],{windowsHide:true,timeout:120000});
 await fs.rename(temporary,target);
 console.log(JSON.stringify({templateId:id,audio:template.audio_file,durationSeconds:template.duration_s,note:'Verify that the source edit and musical cut points match this timing preset.'}));
}catch(error){console.error(error.message);process.exitCode=1;}
