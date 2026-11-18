"""
【导读】week-03 动手 2/2 · 对应 README 模块 D 概念（Day 4-5）+ 周末实战 · 核心练习：TODO 自己填
先修：c_ex_linear_regression.py（训练循环的套路直接复用）｜后续：week-04 b_ex_mlp_mnist.py
运行：python weekend_ex_softmax_regression.py（week-03 目录下；首次会下载 MNIST 到 data/，需先装 torch）
观察：测试集准确率明显高于 10%（瞎猜线）、生成 output/softmax_curve.png（loss 降 + acc 升）

第3周练习② · numpy 手写 softmax 回归
注：2026-11-18 应用户要求填充为「详解注释参考版」（softmax/交叉熵概念判卷已过关）。
    研读重点：TODO 5 注释里的梯度推导（probs - y 为什么成立）——本周最值钱的结论。
    建议读法：盖住实现看注释，能否自己写出代码；读完找私教出代码理解题判卷。

重点体会："softmax + 交叉熵"求导后，输出层梯度形式出奇简洁。
参考：d2l 3.4 https://zh.d2l.ai/chapter_linear-networks/index.html
"""
import numpy as np
from data_utils import load_mnist, one_hot, plot_curves

# 数据已备好（脚手架替你下载）
# 【为什么是这四个数组】数据契约决定模型形状：
#   X:(N,784)——每张 28×28 照片压扁成 784 维向量、归一化到 0-1（详见 data_utils.load_mnist）
#   y:(N,)——0-9 整数标签；train 用来拧旋钮，test 是「密封考卷」只用于最后评估
X_train, y_train, X_test, y_test = load_mnist()   # X:(N,784) y:(N,)
n_in, n_out = 784, 10                             # 输入维度由数据定(784)，输出维度由任务定(10类)
lr = 0.1                                          # 步幅：太大震荡/发散，太小学得慢；0.1 是 softmax 回归常用起点


# ---- TODO 1: 初始化参数 ----
# 【为什么 W 是 (784,10)】每一列 = 一个类别的「784 个旋钮」：
#   第 j 列回答「784 个像素各该多重/多轻，才说明这是第 j 类」。
#   X @ W 一次矩阵乘法 = N 个样本同时过 10 个类别探测器。
# 【为什么随机小数而不是全 0】起点别太偏：全 0 时所有类分数相同、softmax 输出均匀 1/10，
#   虽能学但起步慢；乘 0.01 的小随机数让各类分数略有差异又不至于一开始就「自信地错」
#   （自信地错 → 交叉熵重罚 → 初始 loss 巨大，训练前期浪费在纠偏上）。
# 【为什么 b 可以全 0】偏置只是每类的「基础分」，从公平起点出发即可，没有随机化的必要。
W = np.random.randn(n_in, n_out) * 0.01
b = np.zeros((1, n_out))                          # (1,10)，广播加到每一行样本上


# ---- TODO 2: softmax ----
def softmax(z):
    """把分数变概率，每行和为1。
    数值稳定技巧：先减去每行最大值再取 exp（否则溢出）。"""
    # 【为什么要变概率】原始分数 z 可正可负、量级任意，没法解释也没法当「置信度」。
    #   分类任务需要的是「10 个非负数、和为 1」的分布——才能说「80% 是 7」。
    # 【为什么用 exp 而不是别的】三个性质正好全需要：
    #   ① 输出恒正（负分数也能变正）② 单调递增（分数排名不变）
    #   ③ 放大差距（分数差 1 → 概率差 e≈2.7 倍），让「略高」变成「明显更可能」
    # 整体平移不改变结果：e^{z+c}=e^z·e^c，分子分母的 e^c 约掉（指数函数性质）。
    # 【为什么必须减最大值】float32 下 exp(89) 就溢出成 inf；减最大值后所有元素 ≤0，
    #   exp 最大为 1，永不溢出——而由平移不变性，结果和不移完全一样。
    z = z - z.max(axis=1, keepdims=True)          # 逐行减最大值；keepdims 保持 (N,1) 才能广播
    e = np.exp(z)                                 # 全变正数，且拉大分数差距
    return e / e.sum(axis=1, keepdims=True)       # 逐行归一 → 每行和为 1 的概率分布


# ---- TODO 3: 前向 ----
def forward(X, W, b):
    """scores = X @ W + b ; probs = softmax(scores)。返回 probs。"""
    # X (N,784) @ W (784,10) → (N,10)：N 个样本同时过输出层，得 10 类分数（logits）
    # 再过 softmax：分数 → 概率。这就是「换空间」：像素空间 → 类别概率空间
    return softmax(X @ W + b)


# ---- TODO 4: 交叉熵损失 ----
def cross_entropy(probs, Y_oh):
    """= -sum(Y_oh * log(probs)) / N。加 1e-12 防止 log(0)。"""
    # 【为什么用 -log(p_正确类) 当罚分】它是一条「自信度罚分曲线」：
    #   p=1（答对且满分自信）→ -log(1)=0，不罚
    #   p=0.5（半信半疑）→ 0.69，轻罚
    #   p→0（自信地错）→ -log(p)→∞，重罚
    #   分类要的就是「错得越自信罚越狠」，逼模型把概率质量挪到正确类上。
    # 【为什么乘 Y_oh 再求和】one-hot 只有正确类是 1，其余 0 → 乘积求和实际只剩
    #   「正确类概率取 log 反号」：L = -log(p_正确类)。写成矩阵形式是为了 N 个样本一次算完。
    # 【为什么除以 N】对样本取平均：loss 量级不随批大小变化，
    #   换 batch_size 时不用重调学习率，曲线之间也可比。
    # 【为什么 +1e-12】概率可能算出 0，log(0)=-inf 会污染训练，加个极小量兜底。
    N = probs.shape[0]
    return -np.sum(Y_oh * np.log(probs + 1e-12)) / N


# ---- TODO 5: 训练（含反向传播）----
def train(X, y, W, b, lr, epochs=5, batch_size=128):
    # 【为什么先 one_hot】loss 和梯度都要拿「真实分布」与 probs (N,10) 逐元素运算，
    #   整数标签 7 没法直接减——翻译成 [0,...,1,...,0] 才同形状（详解见 data_utils.one_hot）。
    #   在循环外只做一次：标签不变，没必要每个 batch 重复翻译。
    Y_oh = one_hot(y)                             # (N,10)：标签 → 真实分布
    N = len(X)
    losses, accs = [], []
    for ep in range(epochs):
        # 5a. 打乱索引，分 minibatch
        # 【为什么每轮重新洗牌】① 若数据按类别排序，不打乱则一个 batch 全是同一类，
        #   「小共识」变成「偏见」，梯度猛拽向一类、下一批又拽回来，训练震荡；
        #   ② 每轮 batch 组合不同，噪声方向不同，反而有助于跳出平坦区。
        # 【为什么用 minibatch=128】全量太慢（一步算 6 万行才拧一次旋钮）、
        #   单样本太吵（一行一个私人意见）；128 行的「小共识」折中：稳、更新勤、矩阵并行友好。
        idx = np.random.permutation(N)
        for start in range(0, N, batch_size):
            bi = idx[start:start + batch_size]    # 本批样本的下标
            Xb, Yb = X[bi], Y_oh[bi]              # (128,784) (128,10)

            # 5b. 前向算 probs
            probs = forward(Xb, W, b)             # (128,10)

            # 5c. 反向 ⭐本周最值钱的推导：为什么 dZ = probs - Y_oh ？
            #   设分数 z，概率 p=softmax(z)，损失 L=-Σ_k y_k·log(p_k)
            #   ① softmax 的导数：dp_k/dz_i = p_k·(δ_ki - p_i)
            #      （k=i 时 p_i(1-p_i)；k≠i 时 -p_k·p_i）
            #   ② 链式法则：dL/dz_i = Σ_k (-y_k/p_k)·dp_k/dz_i
            #      = Σ_k (-y_k/p_k)·p_k·(δ_ki - p_i)
            #      = -y_i + p_i·Σ_k y_k
            #   ③ one-hot 的 Σ_k y_k = 1（概率和为1）→ dL/dz_i = p_i - y_i
            #   结论：误差信号 = 预测概率 - 真实分布，和线性回归的 e=y_pred-y 同构！
            #   （对比：MSE 配 softmax 会多出 p(1-p) 因子，自信地错时梯度消失——分类不用 MSE 的原因）
            # 【为什么除以 len(bi)】loss 是批内平均（TODO 4 除了 N），梯度也要同除，
            #   否则梯度量级随 batch_size 缩放，换批大小就得重调 lr。
            dZ = (probs - Yb) / len(bi)           # (128,10)，除以批大小 = 批内平均
            # 【为什么是 Xb.T @ dZ】单样本公式 dW = x·e（像素 × 误差，外积）；
            #   128 个样本要「各算外积再求和」——转置后矩阵乘法恰好一次完成：
            #   Xb.T 的第 i 列 = 第 i 个样本的 x，dZ 的第 i 行 = 它的误差，
            #   (784,128)@(128,10) 的每个元素 = Σ_i x_i·e_i，正是「乘 x 再求和」。
            dW = Xb.T @ dZ                        # (784,128)@(128,10)→(784,10)，与 W 同形
            # 【为什么 db 只求和】z = x@W + b 里 b 的局部导数是 1（加法的汇率恒为 1），
            #   所以 dL/db = Σ 各样本的 dZ，不乘 x；keepdims 保住 (1,10) 与 b 同形。
            db = dZ.sum(axis=0, keepdims=True)    # (1,10)：b 的局部导数是 1，直接对样本求和

            # 5d. 更新参数：照派送清单，每个旋钮往自己汇率的反方向拧一步
            # 【为什么是 -=】梯度指向 loss 上升最快的方向，要下山所以走反方向；
            #   lr 控制步幅。dW 与 W 同形 → 784×10=7840 个旋钮各自按自己的梯度同步拧。
            W -= lr * dW
            b -= lr * db

        # 5e. 每轮末算全量 loss 和 accuracy（epoch 级汇报用全量，step 级才有 batch 噪声）
        # 【为什么汇报用全量】batch 级 loss 随抽样波动（128 行的高方差），画曲线会锯齿；
        #   每轮末用全部训练数据打一次分，才是「这一轮学得怎么样」的稳定读数。
        probs = forward(X, W, b)
        loss = cross_entropy(probs, Y_oh)
        # 【为什么 argmax 就是预测】10 个概率里挑最大的那类 = 模型的最终答案；
        #   与真实标签逐行比对得 True/False，.mean() = 答对比例 = accuracy。
        acc = (probs.argmax(axis=1) == y).mean()  # argmax 取概率最大的类别 = 预测标签
        losses.append(loss)
        accs.append(acc)
        print(f'epoch {ep}  loss={loss:.4f}  acc={acc:.3f}')
    return losses, accs, W, b


def evaluate(X, y, W, b):
    """返回测试集准确率。达标要用测试集，别只看训练集（过拟合陷阱）。"""
    # 【为什么单独一个函数、只前向不更新】考试不许改旋钮：
    #   这里没有 backward、没有 W -=，纯粹用训好的参数答题。
    #   训练集 acc 高不算本事（可能死记硬背）；没见过的测试集才是泛化能力的考卷。
    probs = forward(X, W, b)
    return (probs.argmax(axis=1) == y).mean()


if __name__ == '__main__':
    # 【为什么先取 5000 张】小数据一轮几十步就完，快速验证「代码对不对、loss 降不降」；
    #   确认跑通后再换全量 X_train（把 [:5000] 去掉）冲更高准确率——先跑通再上量。
    losses, accs, W, b = train(X_train[:5000], y_train[:5000], W, b, lr)
    # 【为什么用 X_test 评估】见 evaluate 注释：密封考卷，达标线以它为准。
    print('测试集准确率：', evaluate(X_test, y_test, W, b))
    plot_curves(losses, accs, save='output/softmax_curve.png')