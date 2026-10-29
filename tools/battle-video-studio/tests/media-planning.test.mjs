import test from 'node:test';
import assert from 'node:assert/strict';
import * as selection from '../src/media-selection.ts';
import * as templates from '../scripts/select-template.mjs';
import {normalizeClipInput,videoFrameWindow} from '../src/media-plan.mjs';

const clip=(id,role,seconds,extra={})=>({id,src:`${id}.mp4`,sourceId:id,sourceIn:0,sourceOut:seconds,kind:'video',duration:seconds,width:320,height:240,trimIn:0,trimOut:seconds,role,focalX:50,focalY:50,speed:1,qualityTier:'S',excitement:'exciting',...extra});
const scene=(type,from,duration,extra={})=>({type,from,duration,label:'test',winner:'a',slotIndex:0,...extra});
const job=(clips,scenes)=>({fps:30,renderer:'nine-templates',templateId:'V04',characters:{a:{name:'A',clips},b:{name:'B',clips:[]}},scenes});
const plan=(j)=>{assert.equal(typeof selection.planMedia,'function','prepare must have a real candidate interval planner');return selection.planMedia(j);};
const segments=(p,index=0)=>p.scenes[index].media.a;

test('missing role never silently borrows unrelated footage',()=>{
  assert.throws(()=>selection.selectClip({name:'A',clips:[clip('plate','plate',2)]},'finish',0),/finish|收尾/);
});
test('same project inherits template and selection until explicit change',async()=>{
  assert.equal(typeof templates.selectProjectTemplate,'function');
  const previous={templateId:'V05',templateSelection:{mode:'random',selectedAt:'kept'},renderer:'nine-templates'};
  const inherited=await templates.selectProjectTemplate({},previous);
  assert.equal(inherited.templateId,'V05');
  assert.deepEqual(inherited.templateSelection,previous.templateSelection);
  const changed=await templates.selectProjectTemplate({templateId:'V04'},previous);
  assert.equal(changed.templateId,'V04');assert.equal(changed.templateSelection.mode,'explicit');
});
test('exciting original-speed montage beats a merely long ordinary shot and slowed long shot',()=>{
  const p=plan(job([clip('ordinary','finish',12,{excitement:'ordinary'}),clip('slow','finish',6,{speed:.6}),clip('short1','finish',5),clip('short2','finish',5)],[scene('verdict',0,300)]));
  assert.deepEqual(segments(p).map(s=>s.clip.src),['short1.mp4','short2.mp4']);
  assert.ok(segments(p).every(s=>s.clip.speed===1));
});
test('equally exciting continuous shot stays continuous',()=>{
  const p=plan(job([clip('short1','finish',5),clip('long','finish',12),clip('short2','finish',5)],[scene('verdict',0,300)]));
  assert.equal(segments(p).length,1);assert.equal(segments(p)[0].clip.src,'long.mp4');
});
test('finish assembles disjoint candidates and never loops long display',()=>{
  const p=plan(job([clip('one','finish',3),clip('two','finish',3)],[scene('verdict',0,180)]));
  assert.deepEqual(segments(p).map(s=>s.duration),[90,90]);assert.ok(segments(p).every(s=>!s.loop));
});
test('slowdown is opt-in and its 0.5 boundary still yields actionable shortfall',()=>{
  assert.throws(()=>plan(job([clip('one','finish',3)],[scene('verdict',0,180)])),e=>e.code==='MEDIA_GAPS'&&e.gaps[0].missingSeconds===3);
  const p=plan(job([clip('one','finish',3,{allowSlowdown:true})],[scene('verdict',0,180)]));
  assert.equal(segments(p)[0].clip.speed,.5);
  assert.throws(()=>plan(job([clip('one','finish',3,{allowSlowdown:true})],[scene('verdict',0,210)])),e=>e.code==='MEDIA_GAPS'&&e.gaps[0].role==='finish'&&e.gaps[0].missingSeconds>=.99);
});
test('source intervals prevent renamed/trimmed overlap across intro and finish',()=>{
  const p=plan(job([clip('intro','intro',5,{sourceId:'film',sourceIn:10,sourceOut:15}),clip('renamed','finish',6,{sourceId:'film',sourceIn:12,sourceOut:18}),clip('clean','finish',4,{sourceId:'film',sourceIn:20,sourceOut:24})],[scene('intro',0,150,{layout:'full',subject:'a'}),scene('verdict',150,120)]));
  assert.equal(segments(p,1)[0].clip.src,'clean.mp4');
});
test('A image animation is preferred to poor C gameplay',()=>{
  const p=plan(job([clip('game','finish',12,{qualityTier:'C'}),clip('art','finish',1,{qualityTier:'A',kind:'image',displayDuration:12})],[scene('verdict',0,300)]));
  assert.equal(segments(p)[0].clip.src,'art.mp4');
});
test('fixed plate and character-specific reveal rotation reuse only their own intervals',()=>{
  const clips=[clip('plate','plate',2),clip('h1','highlight',1),clip('h2','highlight',1)];
  const scenes=[scene('compare',0,20),scene('reveal',20,20),scene('reveal',40,20,{winner:'b'}),scene('reveal',60,20),scene('reveal',80,20)];
  const j=job(clips,scenes);j.characters.b.clips=[clip('bp','plate',2),clip('bh','highlight',1)];
  const p=plan(j);
  assert.deepEqual([1,3,4].map(i=>segments(p,i)[0].clip.src),['h1.mp4','h2.mp4','h1.mp4']);
});
test('alternating full intro windows resume the planned source interval',()=>{
  const j=job([clip('ai','intro',4)],[scene('intro',0,60,{layout:'full',subject:'a'}),scene('intro',60,30,{layout:'full',subject:'b'}),scene('intro',90,60,{layout:'full',subject:'a'})]);
  j.templateId='V05';j.characters.b.clips=[clip('bi','intro',1)];
  const p=plan(j);assert.equal(segments(p,2)[0].clip.trimIn,2);assert.equal(segments(p,2)[0].duration,60);
});
test('host-rejected crop is not imported into the plan',()=>{
  assert.throws(()=>plan(job([clip('bad','finish',12,{cropUsable:false})],[scene('verdict',0,120)])),/finish|收尾/);
});
test('invalid trim and speed fail before staging a broken render timeline',()=>{
 for(const raw of [{trimIn:'wat'},{trimOut:Infinity},{speed:0},{speed:.49},{speed:'NaN'},{trimIn:-1},{trimIn:4,trimOut:3},{trimOut:5.1}])assert.throws(()=>normalizeClipInput(raw,{duration:5}),/trim|speed|区间/);
 assert.throws(()=>normalizeClipInput({speed:.5},{duration:5}),/allowSlowdown/);
 const c=normalizeClipInput({trimIn:.01,trimOut:4.99,speed:.5,allowSlowdown:true},{duration:5});
 assert.ok(c.trimIn>=.01&&c.trimOut<=4.99);assert.equal(c.speed,.5);
});
test('only exact, source-disjoint high-quality reveal choices are rotated',()=>{
 const j=job([clip('p','plate',1),clip('h1','highlight',1,{sourceId:'film',sourceIn:1,sourceOut:2}),clip('hcopy','highlight',1,{sourceId:'film',sourceIn:1,sourceOut:2}),clip('h2','highlight',1,{sourceId:'film',sourceIn:3,sourceOut:4}),clip('bad','highlight',1,{qualityTier:'C'})],[scene('reveal',0,20),scene('reveal',20,20)]);
 const p=plan(j);assert.deepEqual(p.scenes.map(s=>s.media.a[0].clip.src),['h1.mp4','h2.mp4']);
});
test('ordinary usable shots precede animated assets, which precede stills at equal quality',()=>{
 const art=clip('art','finish',1,{kind:'image',displayDuration:6});
 const animated=clip('motion','finish',6,{motion:'animated'});
 const ordinary=clip('plain','finish',6,{excitement:'ordinary'});
 assert.equal(segments(plan(job([art,animated,ordinary],[scene('verdict',0,180)])))[0].clip.src,'plain.mp4');
 assert.equal(segments(plan(job([art,animated],[scene('verdict',0,180)])))[0].clip.src,'motion.mp4');
});
test('scarce finish is reserved before a flexible intro with another good option',()=>{
 const clips=[clip('intro-first','intro',4,{sourceId:'film'}),clip('intro-alt','intro',4),clip('only-finish','finish',4,{sourceId:'film'})];
 const p=plan(job(clips,[scene('intro',0,120,{layout:'full',subject:'a'}),scene('verdict',120,120)]));
 assert.equal(segments(p)[0].clip.src,'intro-alt.mp4');assert.equal(segments(p,1)[0].clip.src,'only-finish.mp4');
});
test('a versatile long candidate is allocated into different non-overlapping role intervals',()=>{
 const p=plan(job([clip('versatile','any',20)],[scene('intro',0,120,{layout:'full',subject:'a'}),scene('reveal',120,30),scene('verdict',150,120)]));
 assert.equal(segments(p)[0].duration,120);assert.equal(segments(p,2)[0].duration,120);
 assert.ok(segments(p)[0].clip.sourceOut<=segments(p,2)[0].clip.sourceIn||segments(p,2)[0].clip.sourceOut<=segments(p)[0].clip.sourceIn);
});
test('resuming a half-frame slow interval does not sample the next source shot',()=>{
 const c=clip('slow','intro',2,{trimIn:1/60,trimOut:1.5,speed:.5});
 const w=videoFrameWindow(c,30),frames=89;
 assert.ok(w.before+(frames-1)*c.speed<c.trimOut*30);
 assert.ok(w.before+(frames-1)*c.speed<w.before+w.length);
});

test('known internal cuts are excluded from quick slots even at S tier or role any',()=>{
 for(const [role,type] of [['plate','compare'],['highlight','reveal']]){
  const j=job([clip('hidden-cut','any',2,{continuous:false}),clip('clean',role,1,{qualityTier:'A',continuous:true})],[scene(type,0,20)]);
  if(type==='compare')j.characters.b.clips=[clip('bp','plate',1,{kind:'image'})];
  assert.equal(segments(plan(j))[0].clip.src,'clean.mp4');
  assert.equal(selection.selectClip(j.characters.a,role,0).src,'clean.mp4');
 }
});
test('quick slots never loop or auto-slow a too-short source; a clear still is a fallback',()=>{
 for(const [role,type] of [['plate','compare'],['highlight','reveal']]){
  const j=job([clip('short',role,.3,{continuous:true,allowSlowdown:true})],[scene(type,0,24)]);
  if(type==='compare')j.characters.b.clips=[clip('bp','plate',1,{kind:'image'})];
  assert.throws(()=>plan(j),e=>e.code==='MEDIA_GAPS'&&e.gaps[0].role===role);
  j.characters.a.clips.push(clip('still',role,1,{kind:'image',qualityTier:'A'}));
  const p=plan(j);assert.equal(segments(p)[0].clip.src,'still.mp4');assert.equal(segments(p)[0].loop,false);
 }
});
test('unknown legacy shot continuity is a viewing reminder, never an automatic visual pass',()=>{
 const p=plan(job([clip('legacy','highlight',1)],[scene('reveal',0,20)]));
 assert.ok(p.mediaPlanning.notes.some(n=>n.includes('实际核看')));assert.equal(segments(p)[0].loop,false);
});
