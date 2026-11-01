import test from 'node:test';
import assert from 'node:assert/strict';
import {envelope, segments, valuePoints} from '../../src/web/frontend/src/components/waveformGeometry.ts';
import {sourceTrace} from '../../src/web/frontend/src/components/liveSource.ts';
import {categoryFor, hasFilteredResult, sourceAvailability, sourceSignals, selectSourceTrace} from '../../src/web/frontend/src/components/liveOptions.ts';
import {trendSegments, trendTicks} from '../../src/web/frontend/src/components/trendGeometry.ts';

test('显示信号按实际字段提供，旧记录回退原始值，信号和单位分别选择',()=>{
  const raw={index:0,time_s:0,resp_raw:8388608,ecg_raw:8388608,resp_filtered:null,ecg_filtered:null};
  assert.deepEqual(sourceSignals([raw],'ecg'),['original']);
  assert.equal(selectSourceTrace([raw],'ecg','display',true),'code');
  const sample={...raw,ecg_nominal_mv:0,ecg_baseline_code:0,ecg_baseline_mv:0,ecg_display_code:1,ecg_display_mv:.001,resp_display_code:2};
  assert.deepEqual(sourceSignals([sample],'ecg'),['original','baseline','display']);
  assert.deepEqual(sourceSignals([sample],'resp'),['original','resp']);
  assert.equal(selectSourceTrace([sample],'ecg','display',false),'display_code');
  assert.equal(selectSourceTrace([sample],'ecg','display',true),'display_mv');
  assert.equal(selectSourceTrace([sample],'resp','resp',true),'resp');
  assert.equal(selectSourceTrace([sample],'resp','display',true),'code');
  assert.deepEqual(sourceSignals([{...raw,ecg_display_mv:NaN}],'ecg'),['original']);
});

test('心率趋势跨缺失日期断开，保留孤立的有效日期',()=>{
  assert.deepEqual(trendSegments([null,60,62,null,70,null,72,74]),[[1,2],[4],[6,7]]);
  assert.deepEqual(trendSegments([NaN,Infinity,null]),[]);
  assert.deepEqual(trendSegments([]),[]);
});

test('趋势刻度包含末日，避免相邻末尾标签挤在一起',()=>{
  assert.deepEqual(trendTicks(0),[]);
  assert.deepEqual(trendTicks(1),[0]);
  for(const count of [7,30,90,365]) {
    const ticks=trendTicks(count);
    assert.equal(ticks[0],0);
    assert.equal(ticks.at(-1),count-1);
    assert.equal(new Set(ticks).size,ticks.length);
    assert.ok(ticks.length<=9);
  }
});

test('全部运行模式保留在简化入口下',()=>{
  for(const kind of ['bridge_serial','vendor_serial']) assert.equal(categoryFor(kind),'capture');
  for(const kind of ['bridge_csv','vendor_csv','standard360','standard500']) assert.equal(categoryFor(kind),'file');
  assert.equal(categoryFor('demo'),'demo');
  for(const kind of ['log','result_serial']) assert.equal(categoryFor(kind),'advanced');
});

test('滤波选项同时要求协议声明与有效数据，缺失来源不补造',()=>{
  assert.equal(hasFilteredResult(13,[{filt:null}]),false);
  assert.equal(hasFilteredResult(13,[{filt:12}]),false);
  assert.equal(hasFilteredResult(15,[{filt:null}]),false);
  assert.equal(hasFilteredResult(15,[{filt:0}]),true);
  assert.deepEqual(sourceAvailability([], 'ecg'),{voltage:false,vendor:false});
  const samples=[{ecg_nominal_mv:0,ecg_filtered:null,resp_filtered:2}];
  assert.deepEqual(sourceAvailability(samples,'ecg'),{voltage:true,vendor:false});
  assert.deepEqual(sourceAvailability(samples,'resp'),{voltage:false,vendor:true});
});

test('来源原码、电压与厂商滤波分开，电压缺失不猜测',()=>{
  const samples=[{index:0,time_s:0,resp_raw:8388618,ecg_raw:8388588,resp_filtered:7,ecg_filtered:9,resp_display_code:12,ecg_nominal_mv:-.001},
    {index:2,time_s:.004,resp_raw:8388628,ecg_raw:8388578,resp_filtered:null,ecg_filtered:null}];
  assert.deepEqual(sourceTrace(samples,'vendor_csv','ecg','code').points.map(p=>p.v),[-20,-30]);
  const voltage=sourceTrace(samples,'vendor_csv','ecg','mv');
  assert.match(voltage.unit,/标称mV/);
  assert.deepEqual(voltage.points.map(p=>p.v),[-.001]);
  assert.equal(sourceTrace(samples,'vendor_serial','resp','mv').points.length,0);
  const resp = sourceTrace(samples,'vendor_serial','resp','resp');
  assert.match(resp.unit,/PC呼吸滤波/);
  assert.deepEqual(resp.points.map(p=>p.v),[12]);
  assert.equal(sourceTrace(samples.slice(1),'vendor_serial','resp','resp').points.length,0);
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

test('心电三套数值独立显示，旧数据不临时重算或归一化',()=>{
  const samples=[{index:0,ecg_raw:7088608,resp_raw:8388608,ecg_nominal_mv:-62,
    ecg_baseline_code:60000,ecg_baseline_mv:2.88,ecg_display_code:55000,ecg_display_mv:2.64}];
  for (const [mode,value] of [['code',-1300000],['mv',-62],['baseline_code',60000],['baseline_mv',2.88],['display_code',55000],['display_mv',2.64]]) {
    assert.deepEqual(sourceTrace(samples,'vendor_serial','ecg',mode).points.map(p=>p.v),[value]);
  }
  assert.equal(sourceTrace([{index:0,ecg_raw:7088608}],'vendor_csv','ecg','display_mv').points.length,0);
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
