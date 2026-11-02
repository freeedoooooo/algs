"""
第8周脚手架 · CNN 数据加载 / 可视化 / 画图（可直接运行/导入）

boilerplate：把 FashionMNIST 当成 (B,1,28,28) 图像喂给 CNN（不展平！），
并提供第一层卷积核/特征图可视化工具。搭 CNN 本身（ex_cnn.py）才是学习重点。
"""
import os
import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader


def load_fashion_mnist_image(data_root='./data'):
    """返回 FashionMNIST 作为图像 (N,1,28,28) 0-1，不展平。"""
    from torchvision import datasets, transforms
    tf = transforms.Compose([transforms.ToTensor()])
    tr = datasets.FashionMNIST(root=data_root, train=True, download=True, transform=tf)
    te = datasets.FashionMNIST(root=data_root, train=False, download=True, transform=tf)
    X_train = tr.data.numpy().astype('float32') / 255.0
    y_train = tr.targets.numpy()
    X_test = te.data.numpy().astype('float32') / 255.0
    y_test = te.targets.numpy()
    X_train = np.expand_dims(X_train, 1)      # (N,28,28) -> (N,1,28,28)
    X_test = np.expand_dims(X_test, 1)
    return X_train, y_train, X_test, y_test


def make_cnn_dataloaders(batch_size=128, data_root='./data'):
    X_train, y_train, X_test, y_test = load_fashion_mnist_image(data_root)
    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    test_ds = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    return train_loader, test_loader


def plot_curves(losses, accs=None, save='output/week8_curve.png'):
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(losses, label='loss', color='tab:red')
    ax1.set_xlabel('epoch'); ax1.set_ylabel('loss', color='tab:red')
    if accs is not None:
        ax2 = ax1.twinx()
        ax2.plot(accs, label='acc', color='tab:blue')
        ax2.set_ylabel('accuracy', color='tab:blue')
    plt.title('week8 CNN training curves')
    plt.savefig(save)
    print(f'曲线已存 {save}')


if __name__ == '__main__':
    tr, te = make_cnn_dataloaders()
    xb, yb = next(iter(tr))
    print('CNN 输入 batch shape（应为 (128,1,28,28)）:', tuple(xb.shape))
