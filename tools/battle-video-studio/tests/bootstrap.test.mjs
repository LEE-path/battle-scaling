import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';

test('a relocated installation initializes once and preserves an existing active project',async()=>{
 const folder=await fs.mkdtemp(path.join(os.tmpdir(),'battle-starter-'));
 try{
  await fs.mkdir(path.join(folder,'scripts'));await fs.mkdir(path.join(folder,'data'));
  await fs.copyFile(new URL('../scripts/bootstrap.mjs',import.meta.url),path.join(folder,'scripts/bootstrap.mjs'));
  await fs.writeFile(path.join(folder,'data/starter-job.json'),'starter');
  const {ensureStarter}=await import(pathToFileURL(path.join(folder,'scripts/bootstrap.mjs')).href);
  await ensureStarter();assert.equal(await fs.readFile(path.join(folder,'data/active-job.json'),'utf8'),'starter');
  await fs.writeFile(path.join(folder,'data/active-job.json'),'existing editable project');
  await ensureStarter();assert.equal(await fs.readFile(path.join(folder,'data/active-job.json'),'utf8'),'existing editable project');
 }finally{
  const resolved=path.resolve(folder);
  if(path.dirname(resolved)===path.resolve(os.tmpdir())&&path.basename(resolved).startsWith('battle-starter-'))await fs.rm(resolved,{recursive:true,force:true});
 }
});
