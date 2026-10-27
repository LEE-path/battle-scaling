const $=id=>document.getElementById(id);
let job,templates=[],savedId=null,pollTimer=null;
const api=async(url,options={})=>{const r=await fetch(url,options),data=await r.json();if(!r.ok)throw Error(data.error||r.statusText);return data;};
const post=(url,data)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const message=(text,error=false)=>{$('status').textContent=text;$('status').className=error?'error':'';};
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function readFields(){
  job.id=$('jobId').value;job.title=$('title').value;job.templateId=$('template').value;
  job.characters.a.name=$('aName').value;job.characters.b.name=$('bName').value;
  job.characters.a.version=$('aVersion').value;job.characters.b.version=$('bVersion').value;
  const difficulty=$('difficulty').value||undefined;
  if(difficulty!==job.verdict?.difficulty)job.verdict={...job.verdict,difficultyText:undefined};
  job.verdict={...job.verdict,winner:$('winner').value,subtitle:$('verdictSubtitle').value,difficulty};
  const [width,height]=$('size').value.split('x').map(Number);job.output={width,height,fps:30};
  job.style={...job.style,intensity:Number($('intensity').value),vsVariant:$('vsVariant').value};
  document.querySelectorAll('[data-compare]').forEach(el=>{job.comparisons[Number(el.dataset.compare)][el.dataset.key]=el.value;});
  document.querySelectorAll('[data-clip]').forEach(el=>{const clip=job.characters[el.dataset.side].clips[Number(el.dataset.clip)];if(el.value===''&&['trimOut','speed'].includes(el.dataset.key)){delete clip[el.dataset.key];return;}clip[el.dataset.key]=['role','path','qualityTier','qualityReason'].includes(el.dataset.key)?el.value:Number(el.value);});
  $('raw').value=JSON.stringify(job,null,2);
  return job;
}

function drawClips(side){
  $(side+'Clips').innerHTML=job.characters[side].clips.map((c,i)=>`<div class="clip"><div class="clip-title"><span>${escape(c.path?.split(/[\\/]/).at(-1)||'素材')}</span><button data-remove="${i}" data-side="${side}">×</button></div><label>用途</label><select data-clip="${i}" data-side="${side}" data-key="role">${[['any','自动轮换'],['intro','开场'],['plate','比较底板'],['highlight','单项高光'],['finish','胜者收尾']].map(([v,n])=>`<option value="${v}" ${(c.role||'any')===v?'selected':''}>${n}</option>`).join('')}</select><label>素材优先级（看过画面后选择）</label><select data-clip="${i}" data-side="${side}" data-key="qualityTier">${[['unrated','待看'],['S','S 首选'],['A','A 优质替代'],['B','B 普通可用'],['C','C 最后兜底'],['exclude','排除']].map(([v,n])=>`<option value="${v}" ${(c.qualityTier||'unrated')===v?'selected':''}>${n}</option>`).join('')}</select><input aria-label="选用理由" data-clip="${i}" data-side="${side}" data-key="qualityReason" placeholder="适合这个用途的理由" value="${escape(c.qualityReason||'')}"><div class="row">${[['trimIn','入点',c.trimIn??0],['trimOut','出点',c.trimOut??''],['speed','速度',c.speed??1],['focalX','横焦点',c.focalX??50],['focalY','纵焦点',c.focalY??45]].map(([key,title,value])=>`<div><label>${title}</label><input data-clip="${i}" data-side="${side}" data-key="${key}" type="number" step="0.1" value="${escape(value)}"></div>`).join('')}</div></div>`).join('');
}

function draw(){
  $('title').value=job.title||'';$('jobId').value=job.id||'';$('template').value=job.templateId||'';
  for(const side of ['a','b']){$(side+'Name').value=job.characters[side].name||'';$(side+'Version').value=job.characters[side].version||'';drawClips(side);}
  $('winner').value=job.verdict?.winner||'';$('verdictSubtitle').value=job.verdict?.subtitle||'';$('difficulty').value=job.verdict?.difficulty||'';
  $('size').value=`${job.output?.width||1080}x${job.output?.height||1440}`;$('intensity').value=job.style?.intensity??.65;$('vsVariant').value=job.style?.vsVariant||'silver';
  $('comparisons').innerHTML=(job.comparisons||[]).map((c,i)=>`<div class="compare"><input aria-label="第${i+1}项" data-compare="${i}" data-key="label" value="${escape(c.label)}"><select aria-label="第${i+1}项揭晓者" data-compare="${i}" data-key="winner">${[['','待填写'],['a','A'],['b','B'],['tie','相当']].map(([v,n])=>`<option value="${v}" ${(c.winner||'')===v?'selected':''}>${n}</option>`).join('')}</select></div>`).join('');
  const t=templates.find(t=>t.id===job.templateId);
  if(t){$('slotCount').textContent=`${t.slots}个展示位`;$('musicInfo').textContent=`${t.duration.toFixed(2)}秒 · ${t.slots}个比较位 · ${t.verdict?'单列胜者页':'使用现有片尾呈现结论'}`;}
  $('raw').value=JSON.stringify(job,null,2);
}

async function refreshProjects(){
  const list=await api('/api/projects');$('projects').innerHTML='<option value="">内置演示工程</option>'+list.map(id=>`<option value="${escape(id)}">${escape(id)}</option>`).join('');
}

async function prepare(){
  $('prepare').disabled=true;message('正在导入素材并保存工程…');
  try{
    const result=await post('/api/prepare',readFields());savedId=result.id;$('savedBadge').textContent='已保存 · '+result.id;
    $('studioFrame').src=result.studio;$('studioFrame').hidden=false;$('previewEmpty').hidden=true;$('studioLink').href=result.studio;
    message(`工程已保存，${result.duration.toFixed(2)}秒。可在预览中播放、拖动时间线；也可直接导出。${result.mediaPlanning?.notes?.length?' '+result.mediaPlanning.notes.join(' '):''}`);
    await refreshProjects();$('projects').value=savedId;
    return result;
  }finally{$('prepare').disabled=false;}
}

async function render(scale){
  const prepared=await prepare();
  $('render').disabled=true;$('renderPreview').disabled=true;
  await post('/api/render',{id:prepared.id,scale});
  watchRender(prepared.id);
}

function watchRender(id){
  $('render').disabled=true;$('renderPreview').disabled=true;$('progress').hidden=false;
  clearInterval(pollTimer);
  pollTimer=setInterval(async()=>{
    try{
      const p=await api('/api/progress?id='+encodeURIComponent(id));$('progress').value=p.progress||0;message(p.message||p.stage,p.stage==='error');
      if(p.stage==='done'||p.stage==='error'){
        clearInterval(pollTimer);$('render').disabled=false;$('renderPreview').disabled=false;
        const outputUrl=p.url||(p.stage==='error'?p.lastSuccessfulUrl:undefined);
        if(outputUrl){$('output').hidden=false;$('movie').src=outputUrl+'?v='+Date.now();$('downloadMovie').href=outputUrl;if(p.stage==='error')message((p.message||'渲染失败')+' 下方保留上一版成功输出，可继续播放或保存。',true);}
      }
    }catch(error){message(error.message,true);}
  },1200);
}

for(const side of ['a','b'])$(side+'Files').addEventListener('change',async e=>{
  readFields();
  try{
    for(const file of e.target.files){
      message(`正在导入 ${file.name} …`);
      const r=await api('/api/upload?name='+encodeURIComponent(file.name),{method:'POST',body:file});
      job.characters[side].clips.push({path:r.path,role:'any',trimIn:0,focalX:50,focalY:45});
    }
    draw();message('素材已导入本地。可选择用途、调整入出点和焦点。');
  }catch(error){message(error.message,true);}
});

document.addEventListener('click',e=>{const b=e.target.closest('[data-remove]');if(!b)return;readFields();job.characters[b.dataset.side].clips.splice(Number(b.dataset.remove),1);draw();});
$('template').onchange=()=>{readFields();job.templateSelection={mode:'explicit',selectedAt:new Date().toISOString()};const t=templates.find(t=>t.id===job.templateId);job.comparisons=t.labels.map(label=>({label,winner:''}));draw();message('已按指定方案建立展示位，请从本场评级填写各项揭晓者。');};
$('prepare').onclick=()=>prepare().catch(e=>message(e.message,true));
$('newProject').onclick=()=>{
  const pool=['V01','V02','V03','V04','V05','V06','V07','V08','V09'];const templateId=pool[Math.floor(Math.random()*pool.length)],t=templates.find(t=>t.id===templateId);
  if(!t){message(`抽中了 ${templateId}，但该方案文件缺失，请恢复对应模板后继续。`,true);return;}
  job={id:'battle-'+Date.now(),title:'',mode:'production',templateId,templateSelection:{mode:'random',pool,selectedAt:new Date().toISOString()},
    characters:{a:{name:'',version:'',clips:[]},b:{name:'',version:'',clips:[]}},
    comparisons:t.labels.map(label=>({label,winner:''})),verdict:{winner:'',label:'胜者',subtitle:''},
    output:{width:t.frameSize?.[0]||1080,height:t.frameSize?.[1]||(templateId==='V01'?1920:1440),fps:30},style:{accent:'#edff57',intensity:.65,watermark:'Battle Scaling',textScale:1.15,vsPresentation:'image'}};
  savedId=null;draw();$('savedBadge').textContent='尚未保存';$('studioFrame').hidden=true;$('previewEmpty').hidden=false;$('output').hidden=true;
  message(`已随机抽中 ${templateId}。先按这套方案的音轨和展示位选材，保存或重渲染时保持本次抽签。`);
};
$('render').onclick=()=>render(1).catch(e=>{message(e.message,true);$('render').disabled=false;$('renderPreview').disabled=false;});
$('renderPreview').onclick=()=>render(.5).catch(e=>{message(e.message,true);$('render').disabled=false;$('renderPreview').disabled=false;});
$('loadProject').onclick=async()=>{try{job=await api('/api/project?id='+encodeURIComponent($('projects').value));savedId=$('projects').value||null;draw();message('工程已载入。');}catch(e){message(e.message,true);}};
$('ratingFile').onchange=async e=>{
  try{
    readFields();const imported=JSON.parse(await e.target.files[0].text());
    if(['story','writing','writing-demo'].includes(imported.mode)||imported.sourceKind==='story')throw Error('故事结局不能直接导入为正式视频胜负；请先完成普通PK比较。');
    if(imported.templateId&&imported.characters){job=imported;}
    else{
      if(imported.characters)for(const side of ['a','b'])job.characters[side]={...job.characters[side],...imported.characters[side],clips:job.characters[side].clips};
      job.comparisons=imported.comparisons||imported.dimensions||job.comparisons;
      if(imported.verdict)job.verdict=imported.verdict;
      if(imported.ratingSource)job.ratingSource=imported.ratingSource;
      if(imported.sourceKind)job.sourceKind=imported.sourceKind;
      if(imported.language)job.language=imported.language;
    }
    draw();message('评级比较已导入。请确认音乐容量、双方素材及总判。');
  }catch(e){message('导入失败：'+e.message,true);}
};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(readFields(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=(job.id||'battle-edit')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('applyRaw').onclick=()=>{try{job=JSON.parse($('raw').value);draw();message('任务数据已应用，保存后更新工程预览。');}catch(e){message(e.message,true);}};

try{
  templates=await api('/api/templates');$('template').innerHTML=templates.map(t=>`<option value="${t.id}">${t.id} · ${escape(t.name)} · ${t.slots}位</option>`).join('');
  await refreshProjects();job=await api('/api/project');savedId=job.id;draw();$('projects').value=job.id;message('已载入当前工程。可以预览/导出，或换成自己的评级与素材。');
  const latest=await api('/api/progress?id='+encodeURIComponent(job.id));
  if(latest.stage==='done'&&latest.url?.endsWith('.mp4')){$('output').hidden=false;$('movie').src=latest.url+'?v='+Date.now();$('downloadMovie').href=latest.url;}
  if(['queued','bundling','rendering'].includes(latest.stage))watchRender(job.id);
}catch(error){message(error.message,true);}
