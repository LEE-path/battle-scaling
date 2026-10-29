import React from 'react';
import {Audio,Video} from '@remotion/media';
import {AbsoluteFill,CanvasImage,Freeze,Sequence,staticFile,useCurrentFrame,useVideoConfig} from 'remotion';
import presets from '../data/video-presets.json';
import vsLayout from '../data/vs-layout.json';
import type {Clip,EditJob,Scene} from './types';
import {selectClip,revealOrdinal} from './media-selection';
import {videoFrameWindow} from './media-plan.mjs';
import {TemplateShot,TemplateTransition,TemplateBloom,TemplateAtmosphere,type Profile} from './template-presentation';

const ClipLayer:React.FC<{clip:Clip;width:number;height:number;duration:number;loop:boolean;sourceOffset?:number;planned?:boolean;blurFill?:boolean}>=({clip,width,height,duration,loop,sourceOffset=0,planned=false,blurFill=false})=>{
 const frame=useCurrentFrame();const {fps}=useVideoConfig();const cover=Math.max(width/clip.width,height/clip.height);const w=clip.width*cover,h=clip.height*cover;
 const style:React.CSSProperties={position:'absolute',width:w,height:h,left:(width-w)*clip.focalX/100,top:(height-h)*clip.focalY/100};
 const window=planned?videoFrameWindow(clip,fps):{before:Math.round(clip.trimIn*fps),length:Math.max(1,Math.round((clip.trimOut-clip.trimIn)*fps))};const length=window.length;
 const fill=blurFill&&Math.abs(clip.width/clip.height-width/height)>.01;
 const contain=Math.min(width/clip.width,height/clip.height);const fw=clip.width*contain,fh=clip.height*contain;
 const foreground:React.CSSProperties=fill?{position:'absolute',width:fw,height:fh,left:(width-fw)/2,top:(height-fh)/2}:style;
 // Both layers read the identical source interval and playback clock. Keep the
 // sharp foreground complete; only the soft backdrop is enlarged and cropped.
 const layer=(layerStyle:React.CSSProperties,drawWidth:number,drawHeight:number,animate=false)=>clip.kind==='image'
  ?<CanvasImage src={staticFile(clip.src)} width={Math.round(drawWidth)} height={Math.round(drawHeight)} fit="fill" style={{...layerStyle,scale:animate?1.015+Math.min(1,frame/Math.max(1,duration))*.025:1}}/>
  :<Video src={staticFile(clip.src)} muted trimBefore={Math.round(window.before+sourceOffset*clip.speed)} durationInFrames={Math.max(1,length-Math.round(sourceOffset*clip.speed))} playbackRate={clip.speed} loop={loop&&duration*clip.speed>length} objectFit="fill" style={layerStyle}/>;
 return <AbsoluteFill style={{overflow:'hidden',backgroundColor:'black'}}>
  {fill&&<AbsoluteFill style={{filter:'blur(18px) brightness(0.48)',scale:1.16}}>{layer(style,w,h)}</AbsoluteFill>}
  {layer(foreground,fill?fw:w,fill?fh:h,!fill)}
 </AbsoluteFill>;
};

export const BattleTemplateEdit:React.FC<{job:EditJob}>=({job})=>{
 const frame=useCurrentFrame();const {fps,width,height}=useVideoConfig();const normal=frame*30/fps;const base=(presets as unknown as Record<string,Profile>)[job.templateId];
 const textScale=job.style.textScale??1.15;const logicalHeight=height/(width/540);
 const titleName=(side:'a'|'b')=>job.characters[side].name+(base.id==='V06'&&job.characters[side].version?`（${job.characters[side].version}）`:'');
 const p:Profile={...base,width:540,height:logicalHeight,durationFrames:job.durationInFrames*30/fps,
  title:{...base.title,names:[titleName('a'),titleName('b')],suffix:'',vsAsset:`media/vs/vs-${{silver:'01-silver',ink:'02-ink',prism:'03-prism',comic:'04-comic'}[job.style.vsVariant||'silver']}.png`,vsSize:vsLayout[job.style.vsVariant||'silver'].size,vsBounds:vsLayout[job.style.vsVariant||'silver'].box},
  ending:{...base.ending,brand:job.style.watermark,winner:job.verdict.winner},
 };
 const current=job.scenes.find(s=>frame>=s.from&&frame<s.from+s.duration)||job.scenes.at(-1)!;
 const impact=p.events.find(e=>normal>=e.at+e.peakOffset-Math.max(1,Math.round(p.before*30))&&normal<=e.at+e.peakOffset+Math.max(1,Math.round(p.after*30)));
 const media=(scene:Scene)=>{
  const split=scene.type==='compare'||(scene.type==='intro'&&scene.layout!=='full')||(scene.type==='outro'&&!['V02','V03','V04'].includes(p.id))||(scene.winner==='tie'&&scene.type!=='intro');
  const role=scene.type==='intro'?'intro':split?'plate':scene.type==='reveal'?'highlight':'finish';
  const index=role==='highlight'?revealOrdinal(job.scenes,scene):0;
  const start=scene.media?scene.from:scene.mediaFrom??scene.from;
  const side=scene.type==='intro'?(scene.subject||'a'):scene.winner==='b'?'b':'a';
  if(scene.type==='outro'&&['V02','V03','V04'].includes(p.id))return null;
  const plate=(which:'a'|'b',boxHeight:number)=>{
   const planned=scene.media?.[which];
   if(planned)return <>{planned.map((s,i)=><Sequence key={i} from={s.from} durationInFrames={s.duration} layout="none"><ClipLayer clip={s.clip} width={540} height={boxHeight} duration={s.duration} loop={s.loop} planned blurFill={role==='finish'&&!split}/></Sequence>)}</>;
   const introFor=(s:Scene)=>s.type==='intro'&&(s.layout!=='full'||s.subject===which);
   const earlier=job.scenes.filter(s=>s.from<scene.from&&introFor(s));
   const clip=selectClip(job.characters[which],role,role==='intro'?earlier.length:index);
   // A long montage can serve several alternating windows. Resume its unused
   // interval instead of rewinding the same opening on every return.
   const sourceOffset=role==='intro'&&clip.kind==='video'?earlier.reduce((sum,s,i)=>{
    const previous=selectClip(job.characters[which],'intro',i);
    return sum+(previous.src===clip.src&&previous.trimIn===clip.trimIn&&previous.trimOut===clip.trimOut?s.duration:0);
   },0):0;
   return <ClipLayer clip={clip} width={540} height={boxHeight} duration={scene.duration+(scene.from-start)} sourceOffset={sourceOffset} loop={['plate','highlight'].includes(role)} blurFill={role==='finish'&&!split}/>;
  };
  return <Sequence from={start} layout="none">{split?<AbsoluteFill>
   <div style={{position:'absolute',width:540,height:p.height/2,overflow:'hidden',top:0}}>{plate('a',p.height/2)}</div>
   <div style={{position:'absolute',width:540,height:p.height/2,overflow:'hidden',top:p.height/2}}>{plate('b',p.height/2)}</div>
  </AbsoluteFill>:plate(side,p.height)}</Sequence>;
 };
 const paint=(scene:Scene,f:number)=>{
  const kind=scene.type==='compare'?'label':scene.type==='verdict'?'winner':scene.type;
  const label=kind==='winner'?`${job.characters[scene.winner==='b'?'b':'a'].name}\n${job.verdict.difficultyText||''}`:kind==='outro'?job.style.watermark:scene.label;
  return <>
   <TemplateShot p={p} s={{kind,at:scene.from*30/fps,frames:scene.duration*30/fps,asset:scene.type==='outro'&&['V02','V03','V04'].includes(p.id)?'':'job-media',label}} frame={f} vsPresentation={job.style.vsPresentation||'image'} textScale={textScale} footage={media(scene)}/>
   {scene.showVerdict&&<div style={{position:'absolute',left:'5%',right:'5%',bottom:'7%',textAlign:'center',fontFamily:'"Smiley Sans",sans-serif',fontSize:32*textScale,color:'white',textShadow:'0 2px 5px black',WebkitTextStroke:'.6px black',whiteSpace:'pre-line'}}>{job.characters[job.verdict.winner==='b'?'b':'a'].name}{'\n'}{job.verdict.difficultyText}</div>}
  </>;
 };
 const dissolve=impact?.effect==='dissolve';const target=dissolve?job.scenes.find(s=>Math.abs(s.from-impact.at*fps/30)<1):undefined;
 const prior=target?job.scenes[job.scenes.indexOf(target)-1]:undefined;const blend=target?Math.max(0,Math.min(1,(normal-(impact!.at-5))/7)):1;
 const atmosphere=base.ending.brandAt===null||normal<base.ending.brandAt*30;
 const flicker=p.flicker&&['compare','reveal'].includes(current.type)?Math.max(0,1-Math.abs(((normal-p.introFrames)%20)-2)/2)*.035:0;
 return <AbsoluteFill style={{backgroundColor:'black',fontSynthesis:'none',overflow:'hidden'}}>
  {job.music&&<Audio src={staticFile(job.music)} volume={job.musicVolume}/>}
  <div style={{position:'absolute',width:540,height:p.height,transform:`scale(${width/540})`,transformOrigin:'0 0',overflow:'hidden'}}>
   <TemplateBloom p={p} strength={1}>{target&&prior?<>
    <AbsoluteFill style={{opacity:1-blend}}><Freeze frame={Math.min(frame,target.from-1)}>{paint(prior,Math.min(normal,impact!.at-1))}</Freeze></AbsoluteFill>
    <AbsoluteFill style={{opacity:blend}}><Freeze frame={Math.max(frame,target.from)}>{paint(target,Math.max(normal,impact!.at))}</Freeze></AbsoluteFill>
   </>:<TemplateTransition p={p} impact={impact} frame={normal} enabled>{paint(current,normal)}</TemplateTransition>}</TemplateBloom>
   {atmosphere&&<TemplateAtmosphere frame={normal} p={p} strength={1}/>}
   {flicker>0&&<AbsoluteFill style={{background:'white',opacity:flicker}}/>}
   {p.id==='V07'&&current.type==='outro'&&normal-current.from*30/fps<5&&<AbsoluteFill style={{background:'white',opacity:Math.max(0,1-Math.abs(normal-current.from*30/fps-1)/3)*.8}}/>}
   {job.style.watermark&&(job.style.watermark==='Battle Scaling'?<CanvasImage src={staticFile('media/branding/battle-scaling-watermark.png')} width={524} height={104} fit="fill" style={{position:'absolute',right:12,bottom:12,width:110*textScale,height:110*textScale*104/524}}/>
    :<div style={{position:'absolute',right:12,bottom:12,fontFamily:'"Smiley Sans",sans-serif',fontSize:16*textScale,color:'#fffb',textShadow:'0 1px 2px black'}}>{job.style.watermark}</div>)}
   {['reference-demo','media-demo'].includes(job.mode)&&<div style={{position:'absolute',right:12,top:12,fontFamily:'"Smiley Sans",sans-serif',fontSize:12*textScale,color:'white',background:'#0008',padding:4}}>剪辑功能演示 · 非评级</div>}
  </div>
 </AbsoluteFill>;
};
