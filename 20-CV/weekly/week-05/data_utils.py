"""
第5周脚手架 · 数据与画图（可直接运行/导入）

这些是"boilerplate"——下载 FashionMNIST、画图、数参数量。敲它们学不到 PyTorch 的核心，
所以替你写好。你的精力应全部放在 ex_pytorch_fundamentals.py / ex_train_loop.py 上。
"""
import numpy as np


def load_fashion_mnist(flatten=True, data_root='./data'):
    """下载并返回 FashionMNIST。flatten=True 时展平成 (N,784) 喂给 MLP。
    返回：X_train, y_train, X_test, y_test
    """
    from torchvision import datasets, transforms
    tf = transforms.Compose([transforms.ToTensor()])
    tr = datasets.FashionMNIST(root=data_root, train=True, download=True, transform=tf)
    te = datasets.FashionMNIST(root=data_root, train=False, download=True, transform=tf)

    X_train = tr.data.numpy().astype('float32')
    y_train = tr.targets.numpy()
    X_test = te.data.numpy().astype('float32')
    y_test = te.targets.numpy()

    if flatten:
        X_train = X_train.reshape(len(X_train), -1) / 255.0
        X_test = X_test.reshape(len(X_test), -1) / 255.0
    else:
        X_train = X_train / 255.0
        X_test = X_test / 255.0
    return X_train, y_train, X_test, y_test


def plot_curves(losses, accs=None, save='output/week5_curve.png'):
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
    plt.title('week5 training curves')
    plt.savefig(save)
    print(f'曲线已存 {save}')


def count_params(model):
    """数一个 nn.Module 的总参数量。"""
    return sum(p.numel() for p in model.parameters())


if __name__ == '__main__':
    Xtr, ytr, Xte, yte = load_fashion_mnist()
    print('FashionMNIST:', Xtr.shape, ytr.shape, Xte.shape, yte.shape)
