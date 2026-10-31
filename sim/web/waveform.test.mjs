import test from 'node:test';
import assert from 'node:assert/strict';
import {envelope, segments, valuePoints} from '../../src/web/frontend/src/components/waveformGeometry.ts';

test('抽稀保留尖峰原始时刻，不均匀重排',()=>{
  const original=Array.from({length:10000},(_,index)=>({t:index/500,v:index===1234?100:0}));
  const plotted=envelope(original,100);
  assert.equal(plotted.find(p=>p.v===100).t,1234/500);
  assert.equal(plotted.at(-1).t,9999/500);
  assert.ok(plotted.length<=402);
});
test('抽稀后仍在缺口断线，事件可继续用源时刻',()=>{
  const original=Array.from({length:10000},(_,index)=>({t:(index+(index>=5017?20:0))/500,v:Math.sin(index),breakBefore:index===5017}));
  const lines=segments(envelope(original,100));
  assert.equal(lines.length,2);
  assert.equal(lines[0].at(-1).t,5016/500);
  assert.equal(lines[1][0].t,5037/500);
});
test('末点为(n-1)/fs，不是n/fs',()=>{
  const points=valuePoints([1,2,3],0,3/500,500);
  assert.equal(points.at(-1).t,2/500);
  assert.equal(valuePoints([1,2,3],7,3/500).at(-1).t,7+2/500);
});
