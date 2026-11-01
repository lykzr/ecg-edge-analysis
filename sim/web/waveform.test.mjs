import test from 'node:test';
import assert from 'node:assert/strict';
import {envelope, segments, valuePoints} from '../../src/web/frontend/src/components/waveformGeometry.ts';
import {sourceTrace} from '../../src/web/frontend/src/components/liveSource.ts';

test('来源原码、电压与厂商滤波分开，电压缺失不猜测',()=>{
  const samples=[{index:0,time_s:0,resp_raw:8388618,ecg_raw:8388588,resp_filtered:7,ecg_filtered:9,ecg_nominal_mv:-.001},
    {index:2,time_s:.004,resp_raw:8388628,ecg_raw:8388578,resp_filtered:null,ecg_filtered:null}];
  assert.deepEqual(sourceTrace(samples,'vendor_csv','ecg','code').points.map(p=>p.v),[-20,-30]);
  const voltage=sourceTrace(samples,'vendor_csv','ecg','mv');
  assert.match(voltage.unit,/标称mV/);
  assert.deepEqual(voltage.points.map(p=>p.v),[-.001]);
  assert.equal(sourceTrace(samples,'vendor_serial','resp','mv').points.length,0);
  assert.deepEqual(sourceTrace(samples,'vendor_csv','ecg','vendor').points.map(p=>p.v),[9]);
  assert.equal(sourceTrace(samples,'vendor_csv','ecg','code').points[1].breakBefore,true);
  assert.deepEqual(sourceTrace(samples,'standard500','resp','mv').points.map(p=>p.v),[-20,-30]);
});

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
