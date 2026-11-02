"""
第3周练习② · numpy 手写 softmax 回归（自己填！）

⚠️ 学习规则：
    1. 先自己写，别翻 week-03/README.md 周末部分的代码——那是答案。
    2. 卡住超过 2 小时，看 d2l 3.4-3.6。
    3. 目标：在 MNIST 上训练，准确率能明显高于 10%（瞎猜）。

重点体会："softmax + 交叉熵"求导后，输出层梯度形式出奇简洁。
自己推一遍，别背结论。参考：d2l 3.4 https://zh.d2l.ai/chapter_linear-networks/index.html
"""
import numpy as np
from data_utils import load_mnist, one_hot, plot_curves

# 数据已备好（脚手架替你下载）
X_train, y_train, X_test, y_test = load_mnist()   # X:(N,784) y:(N,)
n_in, n_out = 784, 10
lr = 0.1


# ---- TODO 1: 初始化参数 ----
W = None   # (784,10)
b = None   # (1,10)


# ---- TODO 2: softmax ----
def softmax(z):
    """把分数变概率，每行和为1。
    数值稳定技巧：先减去每行最大值再取 exp（否则溢出）。"""
    raise NotImplementedError


# ---- TODO 3: 前向 ----
def forward(X, W, b):
    """scores = X @ W + b ; probs = softmax(scores)。返回 probs。"""
    raise NotImplementedError


# ---- TODO 4: 交叉熵损失 ----
def cross_entropy(probs, Y_oh):
    """= -sum(Y_oh * log(probs)) / N。加 1e-12 防止 log(0)。"""
    raise NotImplementedError


# ---- TODO 5: 训练（含反向传播）----
def train(X, y, W, b, lr, epochs=5, batch_size=128):
    Y_oh = one_hot(y)
    N = len(X)
    losses, accs = [], []
    for ep in range(epochs):
        # 5a. 打乱索引，分 minibatch
        # 5b. 前向算 probs
        # 5c. 反向：softmax+交叉熵的梯度 = (probs - Y_oh)/N  ← 自己推，别照抄
        #     dW = X_batch.T @ dZ ; db = dZ.sum(axis=0)
        # 5d. 更新参数
        # 5e. 每轮末算全量 loss 和 accuracy，存起来并打印
        raise NotImplementedError
    return losses, accs, W, b


def evaluate(X, y, W, b):
    """返回测试集准确率。达标要用测试集，别只看训练集（过拟合陷阱）。"""
    raise NotImplementedError


if __name__ == '__main__':
    # 建议先取 5000 张小数据跑通，再上全量
    losses, accs, W, b = train(X_train[:5000], y_train[:5000], W, b, lr)
    print('测试集准确率：', evaluate(X_test, y_test, W, b))
    plot_curves(losses, accs, save='softmax_curve.png')
