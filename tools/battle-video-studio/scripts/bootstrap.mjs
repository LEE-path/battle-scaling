import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export async function ensureStarter(){
 await fs.mkdir(path.join(root,'data'),{recursive:true});
 try{await fs.copyFile(path.join(root,'data/starter-job.json'),path.join(root,'data/active-job.json'),1);}catch(error){if(error.code!=='EEXIST')throw error;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await ensureStarter();
