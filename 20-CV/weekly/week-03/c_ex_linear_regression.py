"""
【导读】week-03 动手 1/2 · 对应 README 模块 C（Day 3）· 核心练习：TODO 自己填
先修：模块 A/B 概念+数学（无代码）｜后续：weekend_ex_softmax_regression.py（周末）
运行：python c_ex_linear_regression.py（week-03 目录下，paddle 环境）
观察：loss 一路下降、W→2、b→1、生成 linear_loss.png；加练 lr=1.0 看发散 / 0.001 看学不动

第3周练习① · numpy 手写线性回归
注：2026-11-18 应用户要求填充为「详解注释参考版」（4c 梯度手推判卷已过关）。
    建议读法：先盖住实现，看每步注释能不能自己写出代码，再对照。

数据已备好（y = 2x + 1 + 噪声），模型和训练循环如下。
参考：d2l 第3章 https://zh.d2l.ai/chapter_linear-networks/index.html
"""
import numpy as np
from data_utils import make_regression_data, plot_curves

X, y = make_regression_data(100)     # X:(100,1)  y:(100,1)
lr = 0.1                             # 学习率（试着改大改小，观察发散/学不动）


# ---- 第1步：初始化参数（要训练的「旋钮」）----
# 参数是训练中被调整的对象，不是算出来的结果。
# 形状规则：W = (输入特征数, 本层神经元数)。这里 1 进 1 出，故 (1,1)。
# W 用随机数（打破对称的起点），b 用 0 即可。
W = np.random.randn(1, 1)
b = np.zeros((1, 1))


# ---- 第2步：前向传播（数据从输入算到输出，得到预测值）----
def forward(X, W, b):
    """X (100,1) @ W (1,1) → (100,1)：100 个样本同时过这一层神经元。
    矩阵乘法 = 批量加权求和（换空间描述数据）；+ b = 变换后平移原点（仿射变换）。"""
    return X @ W + b


# ---- 第3步：损失函数（记分牌：预测 vs 真实差多少，一个数）----
def loss_fn(y_pred, y):
    """MSE 均方误差：每个样本的误差平方后取平均。
    平方的作用：正负误差都算「错」，且大误差被放大（错得越离谱罚得越重）。"""
    return np.mean((y_pred - y) ** 2)


# ---- 第4步：训练循环（前向 → 损失 → 反向 → 更新，循环往复）----
def train(X, y, W, b, lr, epochs=100):
    losses = []
    N = len(X)                       # 样本数 100，梯度取平均要用
    for epoch in range(epochs):
        # 4a. 前向：用当前旋钮算预测
        y_pred = forward(X, W, b)    # (100,1)

        # 4b. 损失：给当前表现打分
        loss = loss_fn(y_pred, y)    # 标量

        # 4c. 反向：手推梯度（链式法则，汇率沿依赖链相乘）
        #   单样本：L = (y_pred - y)^2，y_pred = W*x + b
        #     dL/dy_pred = 2(y_pred - y)     ← 规则①：平方求导 = 2×底
        #     dy_pred/dW = x                 ← 规则②：W*x 对 W 求导剩 x
        #     dL/dW = 2(y_pred - y) * x      ← 链式法则：两段相乘
        #   批量：100 个样本各贡献一份，取平均 → (2/N) * Σ x_i·e_i
        #     X.T (1,100) @ e (100,1) → (1,1)
        #     矩阵乘法自动完成「每个样本乘自己的 x，再全部相加」
        e = y_pred - y               # (100,1) 误差信号 = loss 门口出生的「包裹」
        dW = 2 / N * (X.T @ e)       # (1,1) 与 W 同形：每个旋钮领到自己的汇率
        db = 2 / N * np.sum(e)       # b 的局部导数是 1（y_pred=W*x+b 对 b 求导），
                                     # 所以少了「乘 x」，直接把误差求和取平均

        # 4d. 梯度下降：照派送清单，每个旋钮往自己汇率的反方向拧一步
        #     汇率为正 → 拧小；为负 → 拧大。步幅 = 学习率 lr。
        W -= lr * dW
        b -= lr * db

        # 4e. 每轮都存 loss（画曲线用，不能只在打印时存，否则曲线只有10个点）
        losses.append(loss)
        if epoch % 10 == 0:
            print(f'epoch {epoch:3d}  loss={loss:.4f}  W={W[0,0]:.3f}  b={b[0,0]:.3f}')
    return losses, W, b


if __name__ == '__main__':
    losses, W, b = train(X, y, W, b, lr)
    print(f'\n最终 W={W}（应≈2）  b={b}（应≈1）')
    plot_curves(losses, save='output/linear_loss.png')
    # 加练：把 lr 改成 1.0 和 0.001 各跑一次，观察现象，记进 notes.md
    #   lr=1.0   → 步子太大跳过极值点，loss 震荡甚至越荡越大（发散）
    #   lr=0.001 → 100 轮几乎没动，W/b 离真值还很远（学不动）