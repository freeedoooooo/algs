"""
第3-4周共用 · 数据与画图脚手架（可直接运行/导入）

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
    """整数标签 → one-hot。y:(N,) → (N,num_cls)。"""
    N = len(y)
    oh = np.zeros((N, num_cls))
    oh[np.arange(N), y] = 1
    return oh


def plot_curves(losses, accs=None, save='curve.png'):
    """画 loss（和 accuracy）曲线并存图。"""
    import matplotlib.pyplot as plt
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
