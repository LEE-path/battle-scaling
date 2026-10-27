import type {Character, Clip, Scene} from './types';
export {planMedia,sceneMediaSpec} from './media-plan.mjs';

const rank:Record<string,number>={S:4,A:3,B:2,C:1,unrated:0};

export const selectClip=(character:Character,role:string,index:number):Clip=>{
  const usable=character.clips.filter(c=>c.qualityTier!=='exclude'&&c.cropUsable!==false);
  if(!usable.length)throw Error(`${character.name}没有可用素材`);
  const matching=usable.filter(c=>c.role===role||c.role==='any');
  if(!matching.length)throw Error(`${character.name} 缺少适合 ${role} 的素材；请补充该用途候选并设置有效入出点。`);
  const pool=matching;
  const highest=Math.max(...pool.map(c=>rank[c.qualityTier||'unrated']??0));
  // Two curated reveal alternatives may both be excellent even when one is an
  // S video and the other an A image. Never rotate a low-grade fallback in just
  // to reach two; other roles retain their highest-tier preference.
  const floor=role==='highlight'?Math.min(highest,3):highest;
  const seen=new Set<string>();
  const preferred=pool.filter(c=>(rank[c.qualityTier||'unrated']??0)>=floor)
    .sort((a,b)=>(rank[b.qualityTier||'unrated']??0)-(rank[a.qualityTier||'unrated']??0))
    .filter(c=>{
      const key=JSON.stringify([c.src,c.trimIn,c.trimOut]);
      if(seen.has(key))return false;
      seen.add(key);return true;
    });
  return preferred[role==='plate'?0:Math.abs(index)%preferred.length];
};

// Count this character's reveals, not the parity of the global attribute slot.
export const revealOrdinal=(scenes:Scene[],scene:Scene):number=>scenes.filter(s=>
  s.type==='reveal'&&s.winner===scene.winner&&s.from<scene.from).length;
