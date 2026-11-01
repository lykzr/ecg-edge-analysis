/** 有效逐拍最大类别概率的描述统计，不冒充整段诊断置信度。 */
export function beatConfidence(items: {valid: boolean; probabilities: number[] | null}[]) {
  const values = items.filter(b=>b.valid && b.probabilities?.length===3 &&
    b.probabilities.every(p=>Number.isFinite(p) && p>=0 && p<=1) &&
    Math.abs(b.probabilities.reduce((a,b)=>a+b,0)-1)<1e-6)
    .map(b=>Math.max(...b.probabilities!));
  return values.length ? {count:values.length,mean:values.reduce((a,b)=>a+b,0)/values.length,
    min:Math.min(...values),max:Math.max(...values)} : null;
}
