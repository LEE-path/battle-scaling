import React from 'react';
import {Audio, Video} from '@remotion/media';
import {loadFont} from '@remotion/fonts';
import {AbsoluteFill, CanvasImage, Easing, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';

type Segment={kind:string;at:number;frames:number;asset:string;label:string;role?:string};
type Impact={at:number;effect:string;kind:string;peakOffset:number};
export type Profile={id:string;width:number;height:number;durationFrames:number;color:string;effect:string;revealEffect:string;blur:number;shift:number;angle:number;stretch:number;before:number;after:number;introFrames:number;bloom:number;particles:boolean;flicker:boolean;segments:Segment[];events:Impact[];plate:string;title:{mode:string;names:string[];namesAt:number;vsAt:number;vs:string;color:string;vsAsset?:string;suffix?:string;vsSize?:number[];vsBounds?:number[]};ending:{brandAt:number|null;brand:string;fade:number;winner:string|null}};
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const ease={...clamp,easing:Easing.out(Easing.cubic)};
const family='"Smiley Sans","Microsoft YaHei",sans-serif';
void loadFont({family:'Smiley Sans',url:staticFile('fonts/SmileySans-Oblique.ttf'),weight:'400',style:'normal'});
const progress=(x:number,a:number,b:number)=>interpolate(x,[a,b],[0,1],clamp);
const textStyle:React.CSSProperties={fontFamily:family,fontSynthesis:'none',color:'white',textAlign:'center',WebkitTextStroke:'.7px #101014',textShadow:'0 2px 3px #000',lineHeight:1.12};

const Entrance:React.FC<{p:Profile;frame:number;vsPresentation:'image'|'text';textScale:number}>=({p,frame,vsPresentation,textScale})=>{
 const t=frame/30;const v=p.title;if(v.mode==='none')return null;
 const present=v.mode==='present';
 const np=present?1:progress(t,v.namesAt,v.namesAt+(v.mode==='shrink'?.75:.6));
 const vp=present?1:progress(t,v.vsAt,v.vsAt+(v.mode==='together'?.58:.55));
 const name=(i:number)=>v.mode==='typing'?v.names[i].slice(0,Math.floor(np*(v.names[i].length+1))):v.names[i];
 const scale=v.mode==='shrink'?interpolate(np,[0,1],[1.55,1],ease):interpolate(np,[0,1],[.94,1],ease);
 const positions=p.id==='V07'?[{left:'9%',top:'44%',textAlign:'left' as const},{right:'9%',top:'52%',textAlign:'right' as const}]:[{left:0,right:0,top:'40.5%'},{left:0,right:0,top:'54.2%'}];
 const box=v.vsBounds||[53,401,1218,903],size=v.vsSize||[1254,1254],bw=box[2]-box[0],bh=box[3]-box[1];
 return <AbsoluteFill>
  {positions.map((pos,i)=><div key={i} style={{...textStyle,position:'absolute',...pos,fontSize:(p.id==='V06'?26:p.id==='V02'?34:32)*textScale,opacity:v.mode==='typing'?1:np,scale,
    color:p.id==='V03'?(i===0?'#f392a3':'#72d7d0'):'white'}}>{name(i)}{v.suffix&&i===1&&<span style={{fontSize:14*textScale,opacity:progress(t,3.6,4.6)}}>{v.suffix}</span>}</div>)}
  {vsPresentation==='image'?<div style={{position:'absolute',top:'50%',left:'50%',translate:'-50% -50%',width:104,height:104*bh/bw,opacity:vp,scale:interpolate(vp,[0,1],[1.12,1],ease),overflow:'hidden'}}>
    {/* Crop only the transparent canvas margin in layout; the silver emblem
        remains the original supplied PNG and fades as one image layer. */}
    <CanvasImage src={staticFile(v.vsAsset||'media/vs/vs-01-silver.png')} width={size[0]} height={size[1]} fit="fill" style={{position:'absolute',width:104*size[0]/bw,height:104*size[1]/bw,left:-104*box[0]/bw,top:-104*box[1]/bw}}/>
   </div>:<div style={{...textStyle,position:'absolute',top:'50%',left:0,right:0,translate:'0 -50%',fontSize:(p.id==='V02'?40:46)*textScale,color:v.color,opacity:vp,
   letterSpacing:interpolate(vp,[0,1],[20,p.id==='V01'?0:2],clamp),fontStyle:p.id==='V02'||p.id==='V07'?'italic':'normal',scale:interpolate(vp,[0,1],[1.12,1],ease),
   textShadow:p.id==='V04'?'0 0 3px #d51530,0 2px 3px black':'0 2px 3px black'}}>{v.vs}</div>}
 </AbsoluteFill>;
};

// Only bright pixels produce a halo. This is distinct from raising every black
// level or laying a white translucent rectangle over the whole image.
const Bloom:React.FC<{p:Profile;strength:number;children:React.ReactNode}>=({p,strength,children})=>{
 const amount=p.bloom*strength;if(amount<.001)return <>{children}</>;
 const id=`bloom-${p.id}`;
 return <><svg style={{position:'absolute',width:0,height:0}}><defs><filter id={id} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
  <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  1.063 3.576 .361 0 -3.5" result="bright"/>
  <feGaussianBlur in="bright" stdDeviation="5.2" result="halo"/>
  <feComponentTransfer in="halo" result="soft"><feFuncA type="linear" slope={amount}/></feComponentTransfer>
  <feBlend in="SourceGraphic" in2="soft" mode="screen"/>
 </filter></defs></svg><AbsoluteFill style={{filter:`url(#${id})`}}>{children}</AbsoluteFill></>;
};

const Atmosphere:React.FC<{frame:number;p:Profile;strength:number}>=({frame,p,strength})=>{
 if(!p.particles||strength<=0)return null;const t=frame/30;
 return <AbsoluteFill style={{pointerEvents:'none',overflow:'hidden'}}>
  {Array.from({length:32},(_,i)=>{const seed=((i*127.31)%997)/997;const x=((seed*p.width+t*(45+(i%5)*11))%(p.width+160))-80;const y=(((i*83.7)%p.height+t*(72+(i%7)*9))%(p.height+180))-90;
   return <div key={i} style={{position:'absolute',left:x,top:y,width:1.3+(i%3)*.55,height:3+(i%5),rotate:'-32deg',borderRadius:'50%',background:'white',opacity:(.10+(i%4)*.045)*strength,filter:'blur(.4px)'}}/>;})}
 </AbsoluteFill>;
};

const Shot:React.FC<{p:Profile;s:Segment;frame:number;vsPresentation:'image'|'text';textScale?:number;footage?:React.ReactNode}>=({p,s,frame,vsPresentation,textScale=1.15,footage})=>{
 const local=frame-s.at;const k=progress(local,0,Math.max(1,s.frames-1));
 const zoom=s.kind==='reveal'?(p.id==='V01'?interpolate(k,[0,1],[1.015,1.115],ease):interpolate(k,[0,1],[1.012,1.035],clamp)):1;
 const endFade=p.id==='V03'?1-progress(local,57,93):p.id==='V04'?1-progress(local,43,83):p.id==='V05'?1-progress(local,54,61):p.id==='V06'?1-progress(local,26,37):p.id==='V07'?1-progress(local,47,63):1;
 const fade=s.kind==='outro'?endFade:s.kind==='tail'&&p.id==='V08'?1-progress(local,s.frames-33,s.frames-1):s.kind==='winner'&&p.id==='V01'?1-progress(local,s.frames-8,s.frames-1):1;
 const shutterMask=s.kind==='outro'&&p.id==='V09'?progress(local,22,54):0;
 const band=50*(1-shutterMask);const slant=10*shutterMask;
 const clipPath=p.id==='V09'&&s.kind==='outro'?`polygon(0% ${50-band-slant}%,100% ${50-band+slant}%,100% ${50+band+slant}%,0% ${50+band-slant}%)`:undefined;
 const bed=footage!==undefined?footage:s.asset?<Sequence from={s.at} durationInFrames={s.frames+6} layout="none"><Video src={staticFile(s.asset)} muted objectFit="cover" style={{width:p.width,height:p.height}}/></Sequence>:null;
 const isCard=p.id==='V06'&&s.kind==='outro';
 const cardAngle=isCard?interpolate(local,[0,4,10,16,21],[0,0,180,350,360],clamp):0;
 const edgeGlow=isCard?Math.pow(Math.sin(cardAngle*Math.PI/180),2):0;
 const logo=<div style={{...textStyle,whiteSpace:'nowrap',fontSize:Math.min(['V03','V04'].includes(p.id)?58:p.id==='V02'?31:40,p.width*.78/(Math.max(1,s.label.length)*.58))*textScale,letterSpacing:p.id==='V03'?interpolate(local,[0,14],[10,1],ease):2,fontWeight:800,fontStyle:p.id==='V02'?'italic':'normal',
   scale:p.id==='V02'?`${interpolate(local,[0,12],[2.6,1],ease)} ${interpolate(local,[0,12],[.6,1],ease)}`:p.id==='V03'?interpolate(local,[0,14],[1.45,1],ease):1,
   textShadow:['V06','V07'].includes(p.id)?`${Math.sin(local*.7)*2}px 0 2px #62d9ed,${-Math.sin(local*.7)*2}px 0 2px #d36baa`:p.id==='V02'?`${interpolate(local,[0,12],[12,0],clamp)}px 0 4px #b6fd94,${-interpolate(local,[0,12],[12,0],clamp)}px 0 4px #b3a2ff`:'0 0 2px #999',
   background:['V06','V07'].includes(p.id)?`linear-gradient(${110+local*6}deg,#fff 20%,#65f2ff 45%,#cd8feb 60%,#fff 75%)`:undefined,backgroundClip:['V06','V07'].includes(p.id)?'text':undefined,color:['V06','V07'].includes(p.id)?'transparent':'white',
   filter:p.id==='V02'?`blur(${interpolate(local,[0,12],[6,0],clamp)}px)`:undefined}}>{s.label}</div>;
 return <AbsoluteFill style={{backgroundColor:'black',overflow:'hidden'}}>
  {isCard?<AbsoluteFill style={{perspective:800,opacity:fade}}>
    <AbsoluteFill style={{opacity:.3,filter:'blur(1px)'}}>{bed}</AbsoluteFill>
    <AbsoluteFill style={{scale:.72,transform:`rotateY(${cardAngle}deg) rotateZ(${Math.sin(cardAngle*Math.PI/180)*4}deg)`,transformStyle:'preserve-3d',filter:`brightness(${1+edgeGlow*3}) blur(${edgeGlow*3}px)`}}>
     <AbsoluteFill style={{overflow:'hidden'}}>{bed}</AbsoluteFill><AbsoluteFill style={{alignItems:'center',justifyContent:'center'}}>{logo}</AbsoluteFill>
    </AbsoluteFill>
   </AbsoluteFill>:<AbsoluteFill style={{clipPath}}>
    {s.asset&&<AbsoluteFill style={{scale:zoom,opacity:fade}}>{bed}</AbsoluteFill>}
    {s.kind==='outro'&&<AbsoluteFill style={{alignItems:'center',justifyContent:'center',opacity:fade*progress(local,0,5),background:s.asset?'transparent':'black'}}>{logo}</AbsoluteFill>}
   </AbsoluteFill>}
  {s.kind==='intro'&&<Entrance p={p} frame={frame} vsPresentation={vsPresentation} textScale={textScale}/>}
  {s.kind==='label'&&<div style={{...textStyle,position:'absolute',left:0,right:0,top:'50%',translate:'0 -50%',color:p.color,fontSize:(p.id==='V01'?32:44)*textScale}}>{s.label}</div>}
  {s.kind==='winner'&&s.label&&<div style={{...textStyle,position:'absolute',bottom:p.id==='V09'?'4%':'10%',left:0,right:0,fontSize:(p.id==='V09'?31:34)*textScale,whiteSpace:'pre-line',opacity:progress(local,0,4),letterSpacing:p.id==='V03'?5:0}}>{s.label}</div>}
 </AbsoluteFill>;
};

const Transition:React.FC<{p:Profile;impact?:Impact;frame:number;enabled:boolean;children:React.ReactNode}>=({p,impact,frame,enabled,children})=>{
 if(!enabled||!impact||['cut','dissolve'].includes(impact.effect))return <>{children}</>;
 const peak=impact.at+impact.peakOffset;const delta=frame-peak;const range=Math.max(1,Math.round((delta<0?p.before:p.after)*30));const a=Math.max(0,1-Math.abs(delta)/range);
 if(a<.001)return <>{children}</>;
 const fx=impact.effect;const vertical=fx.startsWith('vertical');const horizontal=fx==='horizontal';const sign=delta<0?-1:1;
 const shutter=['V06','V09'].includes(p.id);const spin=p.id==='V05'&&impact.kind==='reveal'?2.5*a*sign:0;
 const id=`directional-${p.id}`;
 return <AbsoluteFill style={{backgroundColor:'black',overflow:'hidden'}}>
  <svg style={{position:'absolute',width:0,height:0}}><defs><filter id={id} x="-70%" y="-70%" width="240%" height="240%" colorInterpolationFilters="sRGB"><feGaussianBlur stdDeviation={`${horizontal?p.blur*a:fx==='swirl'?3*a:1.1*a} ${vertical?p.blur*a:fx==='swirl'?3*a:1.1*a}`} edgeMode="duplicate"/></filter></defs></svg>
  <AbsoluteFill style={{filter:`url(#${id})`,scale:`${1.05+.1*a} ${vertical?1.05+(p.stretch-1)*a:1.05+.1*a}`,translate:`${horizontal?p.shift*a*sign:0}px ${vertical?p.shift*a*sign:0}px`,rotate:`${spin}deg`,opacity:fx==='vertical-dark'?1-.58*a:1,isolation:'isolate'}}>
   {(fx==='swirl'||fx==='zoom'||fx==='diagonal'||shutter)?[-2,-1,0,1,2].map(tap=><AbsoluteFill key={tap} style={{opacity:1/5,mixBlendMode:'plus-lighter',
     rotate:`${fx==='swirl'?tap*p.angle*a/2:shutter?tap*.75*a:0}deg`,translate:fx==='diagonal'?`${tap*p.shift*a/2}px ${tap*p.shift*a*.8/2}px`:shutter?`${tap*7*a}px ${tap*16*a}px`:'0 0',scale:fx==='zoom'?1+(tap+2)/4*a*.44:1}}>{children}</AbsoluteFill>):children}
  </AbsoluteFill>
 </AbsoluteFill>;
};


export {Shot as TemplateShot,Transition as TemplateTransition,Bloom as TemplateBloom,Atmosphere as TemplateAtmosphere};
