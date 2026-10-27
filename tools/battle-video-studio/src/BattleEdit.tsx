import React from 'react';
import {Audio, Video} from '@remotion/media';
import {loadFont} from '@remotion/fonts';
import {AbsoluteFill, CanvasImage, Easing, Interactive, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Character, Clip, EditJob, Scene} from './types';
import {selectClip as chooseClip, revealOrdinal} from './media-selection';
import {videoFrameWindow} from './media-plan.mjs';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const font = '"Smiley Sans", "Microsoft YaHei", Arial, sans-serif';
const vsAssets = {silver:'media/vs/vs-01-silver.png',ink:'media/vs/vs-02-ink.png',prism:'media/vs/vs-03-prism.png',comic:'media/vs/vs-04-comic.png'};
// The supplied face is already slanted; disable synthetic bold/italic at the root.
void loadFont({family:'Smiley Sans',url:staticFile('fonts/SmileySans-Oblique.ttf'),weight:'400',style:'normal'});

const Footage: React.FC<{clip: Clip; duration: number; intensity: number; boxHeight?:number;loop?:boolean;planned?:boolean}> = ({clip, duration, intensity, boxHeight,loop,planned=false}) => {
  const frame = useCurrentFrame();
  const {fps,width,height} = useVideoConfig();
  const targetHeight=boxHeight||height;
  const cover=Math.max(width/clip.width,targetHeight/clip.height);
  const drawWidth=clip.width*cover,drawHeight=clip.height*cover;
  const window=planned?videoFrameWindow(clip,fps):{before:Math.round(clip.trimIn*fps),length:Math.max(1,Math.round((clip.trimOut-clip.trimIn)*fps))};
  const trim=window.before,length=window.length;
  // A fitting shot should finish normally. Unconditional looping can rewind its
  // final displayed frame when source and composition frame rates differ.
  const needsLoop = loop??(duration * clip.speed > length);
  return <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#090a0f'}}>
    <AbsoluteFill style={{
      scale: clip.kind==='image'
        ? interpolate(frame,[0,5,Math.max(6,duration-1)],[1.12+intensity*.04,1.08,1.14],{...clamp,easing:Easing.out(Easing.cubic)})
        : interpolate(frame, [0, 5, Math.max(6, duration-1)], [1.09+intensity*.06, 1.015, 1.045], {...clamp, easing: Easing.out(Easing.cubic)}),
      translate: `${Math.sin(frame*2.4)*Math.max(0,5-frame)*intensity*1.1+(clip.kind==='image'?interpolate(frame,[0,Math.max(1,duration-1)],[-8,8],clamp):0)}px ${interpolate(frame,[0,5],[14*intensity,0],clamp)}px`,
      rotate:clip.kind==='image'?`${interpolate(frame,[0,Math.max(1,duration-1)],[-.45,.45],clamp)*intensity}deg`:'0deg',
      filter: `blur(${interpolate(frame,[0,4],[3.3*intensity,0],clamp)}px)`,
    }}>
      {clip.kind === 'image'
        ? <CanvasImage src={staticFile(clip.src)} width={Math.round(drawWidth)} height={Math.round(drawHeight)} fit="fill"
            style={{position:'absolute',width:drawWidth,height:drawHeight,left:(width-drawWidth)*clip.focalX/100,top:(targetHeight-drawHeight)*clip.focalY/100}} />
        : <Video src={staticFile(clip.src)} muted trimBefore={trim} durationInFrames={length} loop={needsLoop} playbackRate={clip.speed} objectFit="fill"
            style={{position:'absolute',width:drawWidth,height:drawHeight,left:(width-drawWidth)*clip.focalX/100,top:(targetHeight-drawHeight)*clip.focalY/100}} />}
    </AbsoluteFill>
  </AbsoluteFill>;
};

const SceneFootage:React.FC<{job:EditJob;scene:Scene;side:'a'|'b';role:string;index:number;boxHeight?:number}>=({job,scene,side,role,index,boxHeight})=>{
  const planned=scene.media?.[side];
  return planned?<>{planned.map((s,i)=><Sequence key={i} from={s.from} durationInFrames={s.duration} layout="none"><Footage clip={s.clip} duration={s.duration} intensity={job.style.intensity} boxHeight={boxHeight} loop={s.loop} planned/></Sequence>)}</>
    :<Footage clip={chooseClip(job.characters[side],role,index)} duration={scene.duration} intensity={job.style.intensity} boxHeight={boxHeight}/>;
};

const Split: React.FC<{job: EditJob; scene: Scene; intro?: boolean}> = ({job, scene, intro=false}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const role = intro ? 'intro' : 'plate';
  return <AbsoluteFill>
    <div style={{position:'absolute',left:0,right:0,top:0,height:'50%',overflow:'hidden'}}>
      <SceneFootage job={job} scene={scene} side="a" role={role} index={scene.slotIndex} boxHeight={job.height/2}/>
      <AbsoluteFill style={{background:'linear-gradient(0deg,rgba(0,0,0,.54),transparent 45%)'}}/>
    </div>
    <div style={{position:'absolute',left:0,right:0,top:'50%',height:'50%',overflow:'hidden'}}>
      <SceneFootage job={job} scene={scene} side="b" role={role} index={scene.slotIndex} boxHeight={job.height/2}/>
      <AbsoluteFill style={{background:'linear-gradient(180deg,rgba(0,0,0,.48),transparent 45%)'}}/>
    </div>
    {intro ? <AbsoluteFill style={{alignItems:'center',justifyContent:'center',textAlign:'center'}}>
      <div style={{position:'absolute',top:'30%',left:'6%',right:'6%',fontSize:Math.min(94,width*.087),fontWeight:950,WebkitTextStroke:'2px black',textShadow:'0 5px 16px black'}}>
        {job.characters.a.name}
        <div style={{fontSize:38,fontWeight:600,marginTop:9,WebkitTextStroke:'0px',opacity:.92}}>{job.characters.a.version}</div>
      </div>
      <Interactive.Div name="VS emblem" style={{width:Math.min(460,width*.42),height:Math.min(460,width*.42),
        scale:interpolate(frame,[0,8],[1.3,1],{...clamp,easing:Easing.out(Easing.cubic)})}}>
        <CanvasImage src={staticFile(vsAssets[job.style.vsVariant||'silver']||vsAssets.silver)} width={1254} height={1254} fit="contain" style={{width:'100%',height:'100%'}}/>
      </Interactive.Div>
      <div style={{position:'absolute',top:'80%',left:'6%',right:'6%',fontSize:Math.min(94,width*.087),fontWeight:950,WebkitTextStroke:'2px black',textShadow:'0 5px 16px black'}}>
        {job.characters.b.name}
        <div style={{fontSize:38,fontWeight:600,marginTop:9,WebkitTextStroke:'0px',opacity:.92}}>{job.characters.b.version}</div>
      </div>
    </AbsoluteFill> : <>
      <div style={{position:'absolute',top:'50%',left:0,right:0,height:4,background:`linear-gradient(90deg,transparent,${job.style.accent},transparent)`}}/>
      <div style={{position:'absolute',top:'50%',left:'5%',right:'5%',translate:'0 -50%',textAlign:'center',
        scale:interpolate(frame,[0,4,9],[1.28,.98,1],{...clamp,easing:Easing.out(Easing.cubic)})}}>
        <div style={{display:'inline-block',padding:'14px 32px',fontSize:Math.min(90,width*.083),fontWeight:950,color:job.style.accent,
          WebkitTextStroke:'1.6px #101010',textShadow:'0 4px 2px #000, 0 0 24px #000',lineHeight:1.15}}>{scene.label}</div>
        {job.style.showValues && <div style={{fontSize:38,textShadow:'0 2px 8px black'}}>{scene.valueA || ''}{scene.valueA && scene.valueB ? '  /  ' : ''}{scene.valueB || ''}</div>}
      </div>
    </>}
  </AbsoluteFill>;
};

const Reveal: React.FC<{job: EditJob; scene: Scene; final?: boolean}> = ({job,scene,final=false}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  if(scene.winner==='tie') return <>
    <Split job={job} scene={{...scene,label:final ? job.verdict.label : `${scene.label} · 相当`}}/>
    {final && <div style={{position:'absolute',bottom:'10%',width:'100%',textAlign:'center',fontSize:60,fontWeight:800,textShadow:'0 3px 12px black'}}>{job.verdict.subtitle}</div>}
  </>;
  const c = job.characters[scene.winner];
  return <AbsoluteFill>
    <SceneFootage job={job} scene={scene} side={scene.winner} role={final?'finish':'highlight'} index={final?0:revealOrdinal(job.scenes,scene)}/>
    <AbsoluteFill style={{background:'linear-gradient(0deg,rgba(0,0,0,.94),transparent 48%)'}}/>
    <div style={{position:'absolute',bottom:final?'12%':'9%',left:'7%',right:'7%',textAlign:'center',
      opacity:interpolate(frame,[0,3],[0,1],clamp),translate:`0 ${interpolate(frame,[0,6],[32,0],clamp)}px`}}>
      {!final&&<div style={{fontSize:44,fontWeight:800,letterSpacing:4,color:job.style.accent,marginBottom:15,textShadow:'0 2px 12px black'}}>{scene.label}</div>}
      <div style={{fontSize:Math.min(final?132:94,width*(final?.122:.087)),fontWeight:950,WebkitTextStroke:'2px #111',textShadow:'0 5px 15px black',lineHeight:1.25}}>{c.name}</div>
      {final&&<div style={{fontSize:Math.min(116,width*.106),fontWeight:950,marginTop:12,WebkitTextStroke:'2px #111',textShadow:'0 5px 15px black',lineHeight:1.25}}>{job.verdict.difficultyText||'难度：未评定（演示）'}</div>}
      {final && <div style={{fontSize:42,fontWeight:600,marginTop:24,color:'#e3e5e9',lineHeight:1.5}}>{job.verdict.subtitle}</div>}
    </div>
  </AbsoluteFill>;
};

const Shot: React.FC<{job:EditJob;scene:Scene}> = ({job,scene}) => {
  const frame=useCurrentFrame();
  const body=scene.type==='intro' ? <Split job={job} scene={scene} intro/>
    : scene.type==='compare' ? <Split job={job} scene={scene}/>
    : scene.type==='reveal' || scene.type==='verdict' ? <Reveal job={job} scene={scene} final={scene.type==='verdict'}/>
    : <><Split job={job} scene={{...scene,label:'BATTLE SCALING'}}/>
      <div style={{position:'absolute',bottom:'12%',width:'100%',textAlign:'center',fontSize:38,fontWeight:700,textShadow:'0 2px 12px #000'}}>{job.characters.a.name} × {job.characters.b.name}</div></>;
  return <AbsoluteFill>
    {body}
    <AbsoluteFill style={{pointerEvents:'none',backgroundColor:'white',mixBlendMode:'screen',opacity:interpolate(frame,[0,1,3],[.24*job.style.intensity,.06*job.style.intensity,0],clamp)}}/>
  </AbsoluteFill>;
};

export const BattleEdit: React.FC<{job:EditJob}> = ({job}) => {
  const frame=useCurrentFrame();
  return <AbsoluteFill style={{backgroundColor:'#08090c',color:'white',fontFamily:font,fontSynthesis:'none',overflow:'hidden'}}>
    {job.music&&<Audio src={staticFile(job.music)} volume={job.musicVolume}/>}
    {job.scenes.map((scene,i)=><Sequence key={i} name={`${scene.type} / ${scene.label}`} from={scene.from} durationInFrames={scene.duration}>
      <Shot job={job} scene={scene}/>
    </Sequence>)}
    <Interactive.Div name="Watermark" style={{position:'absolute',left:42,bottom:30,fontSize:24,fontWeight:700,letterSpacing:3,opacity:.66,textShadow:'0 2px 8px #000'}}>{job.style.watermark}</Interactive.Div>
    {['reference-demo','media-demo'].includes(job.mode) && <div style={{position:'absolute',right:35,top:32,fontSize:24,background:'#0008',padding:'9px 14px',borderRadius:5}}>{job.mode==='media-demo'?'素材与版式演示 · 非对战评级':'剪辑模板演示'}</div>}
    <AbsoluteFill style={{pointerEvents:'none',backgroundColor:'black',opacity:interpolate(frame,[job.durationInFrames-10,job.durationInFrames-1],[0,1],clamp)}}/>
  </AbsoluteFill>;
};
