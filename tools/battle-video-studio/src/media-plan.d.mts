import type {EditJob,Scene,Clip} from './types';
export function planMedia<T extends {fps:number;renderer?:string;templateId:string;characters:EditJob['characters'];scenes:Scene[]}>(job:T):T & {mediaPlanning:{version:number;notes:string[]}};
export function sceneMediaSpec(job:{renderer?:string;templateId:string},scene:Scene):{role:string;split:boolean;sides:('a'|'b')[]};
export class MediaPlanError extends Error {code:string;gaps:Array<{side:string;character:string;role:string;requiredSeconds:number;availableSeconds?:number;missingSeconds:number;action:string}>;notes:string[]}
export function normalizeClipInput(raw:Record<string,unknown>,meta:{duration:number},options?:{fps?:number;label?:string}):Record<string,number|undefined>;
export function videoFrameWindow(clip:Clip,fps:number):{before:number;length:number};
