import React from 'react';
import {AbsoluteFill,Composition} from 'remotion';
import activeJob from '../data/active-job.json';
import {BattleEdit} from './BattleEdit';
import type {EditJob} from './types';
import {BattleTemplateEdit} from './BattleTemplateEdit';

const RoutedBattleEdit:React.FC<{job:EditJob}>=({job})=>!job.characters.a.clips.length||!job.characters.b.clips.length?<AbsoluteFill style={{backgroundColor:'#10131c',color:'white',alignItems:'center',justifyContent:'center',fontFamily:'sans-serif',textAlign:'center'}}><div>Battle Video Studio<br/>请先导入自己的音轨与双方素材。<br/>Import your music and character media first.</div></AbsoluteFill>:job.renderer==='nine-templates'?<BattleTemplateEdit job={job}/>:<BattleEdit job={job}/>;

export const Root: React.FC = () => {
  return <><Composition
    id="BattleEdit"
    component={RoutedBattleEdit}
    durationInFrames={activeJob.durationInFrames}
    fps={activeJob.fps}
    width={activeJob.width}
    height={activeJob.height}
    defaultProps={{job: activeJob as EditJob}}
    calculateMetadata={({props}) => ({
      durationInFrames: props.job.durationInFrames,
      fps: props.job.fps,
      width: props.job.width,
      height: props.job.height,
      props,
    })}
  /></>;
};
