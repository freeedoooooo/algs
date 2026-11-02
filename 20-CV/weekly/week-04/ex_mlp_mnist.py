"""
第4周练习（P1-A 毕业作品）· 纯 numpy 手写 2 层神经网络训练 MNIST

⚠️⚠️ 学习规则（本周最重要，请遵守）：
    1. backward() 必须自己写，一个字都别抄 week-04/README.md 模块C 的代码
       ——那是"标准答案"，抄了本周价值归零。
    2. 先跑通 forward，再攻 backward，最后组装 train。top-down，别死磕推导。
    3. 卡住超过 2 小时：看 README 模块C / d2l 4.8 / 鱼书第5章。
    4. 达标：测试集准确率 ≥95%，且能对着 backward() 逐行讲清每步在算什么。

结构：784 → 128(隐藏层, ReLU) → 10(输出层, softmax)，交叉熵损失。
参考：d2l 第4章 https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html
"""
import numpy as np

# ===== 数据与工具（boilerplate，已替你写好，不是本周学习重点）=====
def load_mnist(data_root='./data'):
    from torchvision import datasets, transforms
    tf = transforms.Compose([transforms.ToTensor()])
    tr = datasets.MNIST(root=data_root, train=True, download=True, transform=tf)
    te = datasets.MNIST(root=data_root, train=False, download=True, transform=tf)
    Xtr = tr.data.numpy().reshape(-1, 784).astype('float32') / 255.0
    ytr = tr.targets.numpy()
    Xte = te.data.numpy().reshape(-1, 784).astype('float32') / 255.0
    yte = te.targets.numpy()
    return Xtr, ytr, Xte, yte

def one_hot(y, num_cls=10):
    oh = np.zeros((len(y), num_cls)); oh[np.arange(len(y)), y] = 1; return oh

def plot_curves(losses, accs, save='mlp_curve.png'):
    import matplotlib.pyplot as plt
    fig, a1 = plt.subplots(figsize=(8, 4))
    a1.plot(losses, color='tab:red', label='loss'); a1.set_xlabel('epoch')
    a1.set_ylabel('loss', color='tab:red')
    a2 = a1.twinx(); a2.plot(accs, color='tab:blue', label='acc')
    a2.set_ylabel('accuracy', color='tab:blue')
    plt.savefig(save); print(f'曲线已存 {save}')

# ===== 超参 =====
N_IN, N_HID, N_OUT = 784, 128, 10     # 隐藏层太小(如32)可能不够，可试 256
LR = 0.1
np.random.seed(0)


# ---- TODO 1: 初始化参数（He 初始化，配 ReLU）----
# W1:(784,128) 用 randn * sqrt(2/784)；b1:(1,128) 用 0
# W2:(128,10)  用 randn * sqrt(2/10)； b2:(1,10)  用 0
W1 = b1 = W2 = b2 = None


# ---- TODO 2: 激活函数 ----
def relu(z):
    """ReLU = max(0, z)。"""
    raise NotImplementedError

def softmax(z):
    """数值稳定：先减每行最大值再 exp，然后除以每行和。"""
    raise NotImplementedError


# ---- TODO 3: 前向传播 ----
def forward(X):
    """
    Z1 = X @ W1 + b1      (N,128)
    A1 = relu(Z1)         (N,128)
    Z2 = A1 @ W2 + b2     (N,10)
    A2 = softmax(Z2)      (N,10)  每行是类别概率
    返回 Z1, A1, Z2, A2（反向传播要用到这些中间量）
    """
    raise NotImplementedError


# ---- TODO 4: 交叉熵损失 ----
def cross_entropy(probs, Y_oh):
    """= -sum(Y_oh * log(probs + 1e-12)) / N。"""
    raise NotImplementedError


# ---- TODO 5: 反向传播 ⭐本周最难、最值钱，自己写！----
def backward(X, Y_oh, Z1, A1, Z2, A2):
    """
    逐层往回算梯度，用链式法则。shape 提示（务必核对）：
      dZ2 = ?            (N,10)   ← 你在第3周已推过 softmax+交叉熵的输出层梯度，复用那个结论
      dW2 = ?            (128,10) ← 权重梯度 = 上层激活的转置 @ 本层输入梯度
      db2 = ?            (1,10)
      dA1 = ?            (N,128)  ← 从 dZ2 传回：dZ2 @ W2.T
      dZ1 = ?            (N,128)  ← 乘上 ReLU 的导数（想想 ReLU 在正/负区间的导数各是多少）
      dW1 = ?            (784,128)
      db1 = ?            (1,128)
    返回 dW1, db1, dW2, db2
    """
    raise NotImplementedError


# ---- TODO 6: 训练循环（minibatch）----
def train(X, y, epochs=5, batch_size=128, lr=LR):
    global W1, b1, W2, b2
    Y_oh = one_hot(y); N = len(X)
    losses, accs = [], []
    for ep in range(epochs):
        # 6a. idx = np.random.permutation(N) 打乱
        # 6b. 按 batch_size 切片，前向 → 反向 → 更新四个参数
        # 6c. 每轮末：全量前向算 loss 和 acc，存起来并打印
        raise NotImplementedError
    return losses, accs


# ---- TODO 7: 测试集评估（达标看这里，别只看训练集）----
def evaluate(X, y):
    """返回测试集准确率：forward(X)[3].argmax(axis=1) == y 的比例。"""
    raise NotImplementedError


if __name__ == '__main__':
    Xtr, ytr, Xte, yte = load_mnist()
    # 建议先取 5000 张跑通，确认 loss 下降、acc 上升，再上全量
    losses, accs = train(Xtr[:5000], ytr[:5000], epochs=5)
    print('测试集准确率：', evaluate(Xte, yte))   # 目标 ≥95%
    plot_curves(losses, accs)
    # 达标后：对着 backward() 逐行讲解，写进 notes.md（这是 P1-A 验收核心）
