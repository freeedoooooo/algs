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
X_train, y_train, X_test, y_test = load_mnist()   # X:(N,784) y:(N,)
n_in, n_out = 784, 10
lr = 0.1


# ---- TODO 1: 初始化参数 ----
# 形状规则：W = (输入特征数, 输出神经元数) = (784, 10)——784 个像素进、10 个类别分数出。
# 乘 0.01 用小随机数：起点别太偏，softmax 才不至于一开始就「自信地错」。
W = np.random.randn(n_in, n_out) * 0.01
b = np.zeros((1, n_out))                          # (1,10)，广播加到每一行样本上


# ---- TODO 2: softmax ----
def softmax(z):
    """把分数变概率，每行和为1。
    数值稳定技巧：先减去每行最大值再取 exp（否则溢出）。"""
    # 整体平移不改变结果：e^{z+c}=e^z·e^c，分子分母的 e^c 约掉（指数函数性质）。
    # 减最大值后所有元素 ≤0，exp 最大为 1，永不溢出。
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
    # one-hot 只有正确类是 1，其余 0 → 乘积求和实际只剩「正确类概率取 log 反号」：
    #   L = -log(p_正确类) / N（对 N 个样本平均）
    # p→1 时 loss→0（答对且自信不罚）；p→0 时 loss→∞（自信地错重罚）
    # +1e-12：概率可能算出 0，log(0)=-inf 会污染训练，加个极小量兜底
    N = probs.shape[0]
    return -np.sum(Y_oh * np.log(probs + 1e-12)) / N


# ---- TODO 5: 训练（含反向传播）----
def train(X, y, W, b, lr, epochs=5, batch_size=128):
    Y_oh = one_hot(y)                             # (N,10)：标签 → 真实分布
    N = len(X)
    losses, accs = [], []
    for ep in range(epochs):
        # 5a. 打乱索引，分 minibatch
        # 每轮重新洗牌：避免样本顺序带来的偏差；mini-batch = 全量与单样本的折中
        # （梯度是 128 个样本的「小共识」，比单样本稳、比全量更新勤，GPU/矩阵友好）
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
            dZ = (probs - Yb) / len(bi)           # (128,10)，除以批大小 = 批内平均
            dW = Xb.T @ dZ                        # (784,128)@(128,10)→(784,10)，与 W 同形
                                                  # Xb.T 每列一个样本的 x：自动完成「乘 x 再求和」
            db = dZ.sum(axis=0, keepdims=True)    # (1,10)：b 的局部导数是 1，直接对样本求和

            # 5d. 更新参数：照派送清单，每个旋钮往自己汇率的反方向拧一步
            W -= lr * dW
            b -= lr * db

        # 5e. 每轮末算全量 loss 和 accuracy（epoch 级汇报用全量，step 级才有 batch 噪声）
        probs = forward(X, W, b)
        loss = cross_entropy(probs, Y_oh)
        acc = (probs.argmax(axis=1) == y).mean()  # argmax 取概率最大的类别 = 预测标签
        losses.append(loss)
        accs.append(acc)
        print(f'epoch {ep}  loss={loss:.4f}  acc={acc:.3f}')
    return losses, accs, W, b


def evaluate(X, y, W, b):
    """返回测试集准确率。达标要用测试集，别只看训练集（过拟合陷阱）。"""
    # 训练集 acc 高不算本事（可能死记硬背）；没见过的测试集才是泛化能力的考卷
    probs = forward(X, W, b)
    return (probs.argmax(axis=1) == y).mean()


if __name__ == '__main__':
    # 建议先取 5000 张小数据跑通，再上全量
    losses, accs, W, b = train(X_train[:5000], y_train[:5000], W, b, lr)
    print('测试集准确率：', evaluate(X_test, y_test, W, b))
    plot_curves(losses, accs, save='output/softmax_curve.png')