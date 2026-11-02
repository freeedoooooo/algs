"""
第3周练习① · numpy 手写线性回归（自己填！）

⚠️ 学习规则：
    1. 先自己写，别翻 week-03/README.md 模块C 的代码块——那是"标准答案"。
    2. 卡住超过 2 小时，再看 README 或 d2l 3.1-3.3。
    3. 目标：loss 一路下降，W 逼近 2、b 逼近 1。

数据已备好（y = 2x + 1 + 噪声），你只需实现模型和训练循环。
参考：d2l 第3章 https://zh.d2l.ai/chapter_linear-networks/index.html
"""
import numpy as np
from data_utils import make_regression_data, plot_curves

X, y = make_regression_data(100)     # X:(100,1)  y:(100,1)
lr = 0.1                             # 学习率（试着改大改小，观察发散/学不动）


# ---- TODO 1: 初始化参数 ----
# W 形状应为 (1,1)，b 形状 (1,1)。用 np.random.randn 初始化 W，b 用 0。
W = None
b = None


# ---- TODO 2: 前向传播 ----
def forward(X, W, b):
    """返回预测值。提示：线性模型就是 X @ W + b。"""
    raise NotImplementedError


# ---- TODO 3: 损失函数 ----
def loss_fn(y_pred, y):
    """均方误差 MSE = mean((y_pred - y)^2)。返回一个标量。"""
    raise NotImplementedError


# ---- TODO 4: 训练循环 ----
def train(X, y, W, b, lr, epochs=100):
    losses = []
    for epoch in range(epochs):
        # 4a. 前向：算 y_pred
        # 4b. 算 loss
        # 4c. 反向：手推梯度
        #     dW = 2/N * X.T @ (y_pred - y)     ← 自己推一遍为什么，别照抄
        #     db = 2/N * sum(y_pred - y)
        # 4d. 梯度下降：W -= lr*dW ; b -= lr*db
        # 4e. 每 10 轮打印 loss、W、b，并把 loss 存进 losses
        raise NotImplementedError
    return losses, W, b


if __name__ == '__main__':
    losses, W, b = train(X, y, W, b, lr)
    print(f'\n最终 W={W}（应≈2）  b={b}（应≈1）')
    plot_curves(losses, save='linear_loss.png')
    # 加练：把 lr 改成 1.0 和 0.001 各跑一次，观察现象，记进 notes.md
