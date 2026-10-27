import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {ROOT,prepareJob,slug} from './prepare-job.mjs';
import {ensureStarter} from './bootstrap.mjs';

await ensureStarter();
const PORT=3210;
const STUDIO=3211;
let studioProcess=null;
let renderProcess=null;
let renderId=null;
const processFile=path.join(ROOT,'data','processes.local.json');
let retainedStudioPid=null;
try{retainedStudioPid=JSON.parse(await fs.readFile(processFile,'utf8')).studio||null;}catch{}
const saveProcesses=()=>fs.writeFile(processFile,JSON.stringify({server:process.pid,studio:studioProcess?.pid||retainedStudioPid,render:renderProcess?.exitCode===null?renderProcess.pid:null}));
const json=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const body=async req=>{
  const chunks=[];let bytes=0;
  for await(const chunk of req){bytes+=chunk.length;if(bytes>5*1024*1024)throw Error('任务JSON过大。视频请使用素材上传入口。');chunks.push(chunk);}
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
};
async function startStudio(){
  if(studioProcess && studioProcess.exitCode===null)return;
  try{const existing=await fetch(`http://127.0.0.1:${STUDIO}`,{signal:AbortSignal.timeout(500)});if(existing.ok){void saveProcesses();return;}}catch{}
  retainedStudioPid=null;
  studioProcess=spawn(process.execPath,[path.join(ROOT,'node_modules','@remotion','cli','remotion-cli.js'),'studio',path.join(ROOT,'src','index.ts'),'--port',String(STUDIO),'--no-open'],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});
  studioProcess.stdout.on('data',chunk=>process.stdout.write(chunk));studioProcess.stderr.on('data',chunk=>process.stderr.write(chunk));
  void saveProcesses();
}
const contentTypes={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.mp4':'video/mp4','.m4a':'audio/mp4','.png':'image/png','.jpg':'image/jpeg','.json':'application/json; charset=utf-8'};

const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,`http://127.0.0.1:${PORT}`);
  try {
    if(req.method==='GET' && url.pathname==='/api/templates'){
      const files=(await fs.readdir(path.join(ROOT,'templates'))).filter(f=>f.endsWith('.json'));
      const templates=await Promise.all(files.map(f=>read(path.join(ROOT,'templates',f))));
      return json(res,200,templates.map(t=>({id:t.id,name:t.reference,slots:t.comparison_slot_count,verdict:t.dedicated_verdict_slot_count,duration:t.duration_s,frameSize:t.frame_size,labels:t.slots.filter(s=>s.original_role!=='verdict').map(s=>s.original_label)})));
    }
    if(req.method==='GET' && url.pathname==='/api/project'){
      const id=url.searchParams.get('id');
      if(id)return json(res,200,await read(path.join(ROOT,'projects',slug(id),'job.json')));
      const active=await read(path.join(ROOT,'data','active-job.json')).catch(()=>null);
      return json(res,200,active?await read(path.join(ROOT,'projects',slug(active.id),'job.json')).catch(()=>read(path.join(ROOT,'examples','reference-demo.json'))):await read(path.join(ROOT,'examples','reference-demo.json')));
    }
    if(req.method==='GET' && url.pathname==='/api/projects'){
      const files=await fs.readdir(path.join(ROOT,'projects')).catch(()=>[]);
      return json(res,200,files);
    }
    if(req.method==='POST' && url.pathname==='/api/upload'){
      const name=slug(url.searchParams.get('name')||'media.mp4');
      const folder=path.join(ROOT,'public','uploads');await fs.mkdir(folder,{recursive:true});
      const filename=path.join(folder,`${Date.now()}-${name}`);
      const handle=await fs.open(filename,'wx');
      let count=0;
      try{for await(const chunk of req){count+=chunk.length;if(count>4*1024*1024*1024)throw Error('单个素材超过4GB。可改用本地绝对路径。');await handle.write(chunk);}}finally{await handle.close();}
      return json(res,200,{path:filename,name});
    }
    if(req.method==='POST' && url.pathname==='/api/prepare'){
      if(renderProcess && renderProcess.exitCode===null)return json(res,409,{error:'正在渲染当前工程，请完成后再改任务。'});
      const result=await prepareJob(await body(req));await startStudio();
      return json(res,200,{id:result.id,projectFile:result.projectFile,studio:`http://127.0.0.1:${STUDIO}/BattleEdit`,duration:result.compiled.durationInFrames/result.compiled.fps,mediaPlanning:result.compiled.mediaPlanning});
    }
    if(req.method==='POST' && url.pathname==='/api/render'){
      if(renderProcess && renderProcess.exitCode===null)return json(res,409,{error:'已有渲染任务在进行。'});
      const args=await body(req);renderId=slug(args.id);
      const outputFolder=path.join(ROOT,'outputs',renderId);await fs.mkdir(outputFolder,{recursive:true});
      const previous=await read(path.join(outputFolder,'progress.json')).catch(()=>null);
      await fs.writeFile(path.join(outputFolder,'progress.json'),JSON.stringify({id:renderId,stage:'queued',progress:0,lastSuccessfulOutput:previous?.stage==='done'?previous.output:previous?.lastSuccessfulOutput,message:'准备渲染'}));
      renderProcess=spawn(process.execPath,[path.join(ROOT,'scripts','render-job.mjs'),'--job',renderId,'--scale',String(args.scale||1)],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});
      renderProcess.stdout.on('data',chunk=>process.stdout.write(chunk));renderProcess.stderr.on('data',chunk=>process.stderr.write(chunk));
      renderProcess.on('exit',code=>{if(code)void (async()=>{const progress=await read(path.join(outputFolder,'progress.json')).catch(()=>null);if(progress?.stage!=='error')await fs.writeFile(path.join(outputFolder,'progress.json'),JSON.stringify({...progress,id:renderId,stage:'error',progress:0,message:'渲染未完成，请查看 data/server.stderr.log 的具体错误。'}));})();void saveProcesses();});
      void saveProcesses();
      return json(res,202,{id:renderId});
    }
    if(req.method==='GET' && url.pathname==='/api/progress'){
      const id=slug(url.searchParams.get('id')||renderId||'none');
      const data=await read(path.join(ROOT,'outputs',id,'progress.json')).catch(()=>({stage:'idle',progress:0,message:'尚未渲染'}));
      if(data.output)data.url='/outputs/'+encodeURIComponent(id)+'/'+encodeURIComponent(path.basename(data.output));
      if(data.lastSuccessfulOutput)data.lastSuccessfulUrl='/outputs/'+encodeURIComponent(id)+'/'+encodeURIComponent(path.basename(data.lastSuccessfulOutput));
      return json(res,200,data);
    }
    let filename;
    if(url.pathname.startsWith('/outputs/'))filename=path.resolve(ROOT,'.'+decodeURIComponent(url.pathname));
    else filename=path.resolve(ROOT,'workbench',url.pathname==='/'?'index.html':'.'+decodeURIComponent(url.pathname));
    const allowed=url.pathname.startsWith('/outputs/')?path.join(ROOT,'outputs')+path.sep:path.join(ROOT,'workbench')+path.sep;
    if(!filename.startsWith(allowed))return json(res,403,{error:'无效路径'});
    const stat=await fs.stat(filename);
    const range=req.headers.range;
    const {createReadStream}=await import('node:fs');
    if(range){
      const m=/bytes=(\d+)-(\d*)/.exec(range);if(!m)return json(res,416,{error:'无效范围'});
      const start=Number(m[1]),end=m[2]?Math.min(Number(m[2]),stat.size-1):stat.size-1;
      if(start>end||start>=stat.size){res.writeHead(416,{'Content-Range':`bytes */${stat.size}`});return res.end();}
      res.writeHead(206,{'Content-Type':contentTypes[path.extname(filename)]||'application/octet-stream','Content-Length':end-start+1,'Content-Range':`bytes ${start}-${end}/${stat.size}`,'Accept-Ranges':'bytes'});
      createReadStream(filename,{start,end}).pipe(res);
    }else{
      res.writeHead(200,{'Content-Type':contentTypes[path.extname(filename)]||'application/octet-stream','Content-Length':stat.size,'Accept-Ranges':'bytes'});createReadStream(filename).pipe(res);
    }
  }catch(error){json(res,400,{error:error.message,...(error.code==='MEDIA_GAPS'?{code:error.code,gaps:error.gaps,notes:error.notes}:{})});}
});

server.listen(PORT,'127.0.0.1',()=>{console.log(`Battle Video Studio: http://127.0.0.1:${PORT}`);startStudio();});
server.on('error',error=>{console.error(error.message);process.exitCode=1;});
const shutdown=()=>{studioProcess?.kill();renderProcess?.kill();server.close();};
process.on('SIGINT',shutdown);process.on('SIGTERM',shutdown);
