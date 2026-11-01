// 心率缺失的日期断开折线，不把缺失数据连成趋势。
export function trendSegments(values: (number | null)[]): number[][] {
  const result: number[][]=[];
  let current: number[]=[];
  values.forEach((value,index)=>{
    if(value==null || !Number.isFinite(value)) {
      if(current.length)result.push(current);
      current=[];
    } else current.push(index);
  });
  if(current.length)result.push(current);
  return result;
}

export function trendTicks(count:number): number[] {
  if(count<=0)return [];
  const step=Math.max(1,Math.ceil(count/8));
  const ticks=[0];
  for(let index=step;index<count-1;index+=step) {
    if(count-1-index>=step/2)ticks.push(index);
  }
  if(count>1)ticks.push(count-1);
  return ticks;
}
