"""部署准备数值参考：对称INT8、INT32累加、右移最近舍入且中点远离零。"""
def requantize(acc, shift, relu=False):
    if type(acc) is not int or not -(1<<31)<=acc<(1<<31):raise ValueError('累加溢出INT32')
    if type(shift) is not int or not 0<=shift<=31:raise ValueError('shift须0..31')
    value=((abs(acc)+(1<<(shift-1)))>>shift) if shift else abs(acc)
    if acc<0:value=-value
    return max(0 if relu else -128,min(127,value))

def conv1d_valid(x,w,bias,shift,relu=False):
    # x[输入通道][时间]；w[输出通道][输入通道][核位置]，只做valid/stride1。
    if not x or not w or not x[0]:raise ValueError('空张量')
    length=len(x[0]);channels=len(x);kernel=len(w[0][0])
    if not kernel or kernel>length or len(bias)!=len(w):raise ValueError('卷积维度错误')
    if any(len(row)!=length for row in x):raise ValueError('输入长度不一致')
    if any(len(f)!=channels or any(len(row)!=kernel for row in f) for f in w):raise ValueError('权重维度错误')
    values=[v for row in x for v in row]+[v for f in w for row in f for v in row]
    if any(type(v) is not int or not -128<=v<=127 for v in values):raise ValueError('张量必须INT8')
    if any(type(b) is not int or not -(1<<31)<=b<(1<<31) for b in bias):raise ValueError('偏置必须INT32')
    # 用最坏绝对值界拒绝可能溢出配置，硬件前提同此检查。
    if any(abs(b)+channels*kernel*16384>2147483647 for b in bias):raise ValueError('配置可能累加溢出')
    return [[requantize(bias[o]+sum(x[c][t+k]*w[o][c][k] for c in range(channels) for k in range(kernel)),shift,relu)
             for t in range(length-kernel+1)] for o in range(len(w))]

def maxpool1d(x,width):
    if type(width) is not int or width<=0:raise ValueError('池化宽度错误')
    if not x or not x[0] or width>len(x[0]) or any(len(row)!=len(x[0]) for row in x):raise ValueError('池化张量错误')
    if any(type(v) is not int or not -128<=v<=127 for row in x for v in row):raise ValueError('池化张量必须INT8')
    return [[max(row[t:t+width]) for t in range(0,len(row)-width+1,width)] for row in x]
