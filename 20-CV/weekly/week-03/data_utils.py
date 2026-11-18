"""
第3-4周共用 · 数据与画图脚手架（可直接运行/导入）
【导读】共享脚手架，不计入动手顺序；本周动手文件见 README「动手顺序表」

这些是"boilerplate"——下载数据、one-hot、画曲线，敲它们学不到深度学习，
所以替你写好。你的精力应该全部放在 ex_*.py 里手写模型和梯度上。
"""
import numpy as np


def make_regression_data(n=100, seed=0):
    """造线性回归数据：y = 2x + 1 + 噪声。返回 X(n,1), y(n,1)。"""
    np.random.seed(seed)
    X = np.random.randn(n, 1)
    y = 2 * X + 1 + 0.1 * np.random.randn(n, 1)
    return X, y


def load_mnist(flatten=True, data_root='./data'):
    """下载并返回 MNIST。flatten=True 时展平成 (N,784) 并归一化到 0-1。
    返回：X_train, y_train, X_test, y_test
    """
    from torchvision import datasets, transforms
    tf = transforms.Compose([transforms.ToTensor()])
    train = datasets.MNIST(root=data_root, train=True, download=True, transform=tf)
    test = datasets.MNIST(root=data_root, train=False, download=True, transform=tf)

    X_train = train.data.numpy().astype('float32')
    y_train = train.targets.numpy()
    X_test = test.data.numpy().astype('float32')
    y_test = test.targets.numpy()

    if flatten:
        X_train = X_train.reshape(len(X_train), -1) / 255.0
        X_test = X_test.reshape(len(X_test), -1) / 255.0
    else:
        X_train = X_train / 255.0
        X_test = X_test / 255.0
    return X_train, y_train, X_test, y_test


def one_hot(y, num_cls=10):
    """整数标签 → one-hot。y:(N,) → (N,num_cls)。

    【为什么要做这一步】
    模型输出 probs 是 (N,10) 的「概率分布」——每行 10 个数、和为 1。
    而原始标签 y 是 (N,) 的整数（比如 7），一个整数没法和 10 维向量做减法/乘法：
      - 交叉熵 L = -Σ_k y_k·log(p_k) 需要「真实分布 y_k」逐类去乘
      - 梯度 dZ = probs - Y_oh 需要两边同形状 (N,10) 才能对减
    所以把整数标签「翻译」成和 probs 同形状的真实分布：
      标签 7 → [0,0,0,0,0,0,0,1,0,0]
    含义 = 「正确答案是第 7 类，置信度 100%」——一个不含任何不确定性的理想分布。
    这样「预测分布 vs 真实分布」就能逐元素比较了，loss 和梯度公式才写得出来。

    【代码怎么实现】
    oh[np.arange(N), y] = 1 是 numpy 的「成对索引」：
      np.arange(N) = [0,1,2,...,N-1] 提供行号，y = [7,2,0,...] 提供列号，
      两两配对 → 第 0 行第 7 列、第 1 行第 2 列……各置 1，其余保持 0。
      等价于 for i in range(N): oh[i, y[i]] = 1，但一行向量化写完。
    """
    N = len(y)
    oh = np.zeros((N, num_cls))                   # 先全 0：默认「每个类都不是答案」
    oh[np.arange(N), y] = 1                       # 每行只在正确类别那一列点亮 1
    return oh


def plot_curves(losses, accs=None, save='output/curve.png'):
    """画 loss（和 accuracy）曲线并存图。产物统一放 output/。"""
    import os
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(losses, label='loss', color='tab:red')
    ax1.set_xlabel('epoch'); ax1.set_ylabel('loss', color='tab:red')
    if accs is not None:
        ax2 = ax1.twinx()
        ax2.plot(accs, label='acc', color='tab:blue')
        ax2.set_ylabel('accuracy', color='tab:blue')
    plt.title('training curves')
    plt.savefig(save)
    print(f'曲线已存 {save}')


if __name__ == '__main__':
    X, y = make_regression_data()
    print('回归数据:', X.shape, y.shape)
    Xtr, ytr, Xte, yte = load_mnist()
    print('MNIST:', Xtr.shape, ytr.shape, Xte.shape, yte.shape)
    print('one_hot 示例:', one_hot(np.array([3, 7]))[0])
