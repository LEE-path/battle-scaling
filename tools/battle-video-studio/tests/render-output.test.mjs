import test from 'node:test';
import assert from 'node:assert/strict';
import * as rendering from '../scripts/render-job.mjs';
test('rerender uses a new filename so an open player cannot lock the next export',()=>{
 assert.equal(typeof rendering.renderOutputName,'function');
 const a=rendering.renderOutputName({id:'audit',scale:.5,frameRange:[3,9]});
 const b=rendering.renderOutputName({id:'audit',scale:.5,frameRange:[3,9]});
 assert.notEqual(a,b);assert.match(a,/audit-frames-3-9-preview.*\.mp4$/);
});

test('fractional previews use the nearest exact even-pixel scale without aspect distortion',()=>{
 const scale=rendering.compatibleVideoScale({width:1080,height:1440,scale:.35});
 assert.ok(Math.abs(scale-.35)<.01);
 assert.ok(Number.isInteger(1080*scale)&&Number.isInteger(1440*scale));
 assert.equal((1080*scale)%2,0);assert.equal((1440*scale)%2,0);
 assert.equal(rendering.compatibleVideoScale({width:1080,height:1440,scale:.5}),.5);
 assert.equal(rendering.compatibleVideoScale({width:1080,height:1440,scale:1}),1);
});
