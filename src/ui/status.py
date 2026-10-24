"""状态文案纯函数；不推断物理断连、不把历史值或未知类别当实时正常。"""
def bridge_status(info, active):
 error=info.get('error')
 if error:return '出错：'+str(error)+' · 显示历史数据',True,True
 if not active:
  reason=info.get('reason');text={'completed':'完整运行结束','stopped_by_user':'已手动停止'}.get(reason,'未完整完成')
  return text+' · 显示历史数据',reason not in ('completed','stopped_by_user'),True
 age=info.get('sample_age_s')
 if age is not None and age>2:return '暂无新波形（不等于断连）· 显示历史数值',False,True
 states={'starting':'准备中','connecting':'等待板端确认','running':'送样并接收结果','draining':'停止来源，正在收尾'}
 return '中转中 · '+states.get(info.get('state'),str(info.get('state'))),False,False
