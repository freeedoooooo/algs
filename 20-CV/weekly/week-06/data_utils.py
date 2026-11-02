"""
第6周脚手架 · 数据加载器 / 模型保存 / 画图（可直接运行/导入）

boilerplate：把 FashionMNIST 切成 train/val/test，提供 TensorDataset+DataLoader，
以及模型 state_dict 的保存/加载。敲这些学不到深度学习，替你写好。
"""
import os
import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader, random_split


def load_fashion_mnist(flatten=True, data_root='./data'):
    """下载并返回 FashionMNIST（展平版，喂 MLP）。"""
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


def make_dataloaders(batch_size=128, val_ratio=0.1, seed=0):
    """返回 (train_loader, val_loader, test_loader)。
    FashionMNIST 官方是 60k 训练 + 10k 测试；这里把 60k 再拆出 10% 当验证集。
    """
    X_train, y_train, X_test, y_test = load_fashion_mnist(flatten=True)
    full_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    n_val = int(len(full_ds) * val_ratio)
    g = torch.Generator().manual_seed(seed)
    train_ds, val_ds = random_split(full_ds, [len(full_ds) - n_val, n_val], generator=g)
    test_ds = TensorDataset(torch.from_numpy(X_test), torch.from_numpy(y_test))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    return train_loader, val_loader, test_loader


def save_model(model, path='output/best_model.pt'):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    torch.save(model.state_dict(), path)
    print(f'模型已存 {path}')


def load_model(model, path='output/best_model.pt'):
    model.load_state_dict(torch.load(path, map_location='cpu'))
    print(f'模型已从 {path} 载入')
    return model


def plot_curves(losses, accs=None, save='output/week6_curve.png'):
    import matplotlib.pyplot as plt
    os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(losses, label='loss', color='tab:red')
    ax1.set_xlabel('epoch'); ax1.set_ylabel('loss', color='tab:red')
    if accs is not None:
        ax2 = ax1.twinx()
        ax2.plot(accs, label='acc', color='tab:blue')
        ax2.set_ylabel('accuracy', color='tab:blue')
    plt.title('week6 training curves')
    plt.savefig(save)
    print(f'曲线已存 {save}')


if __name__ == '__main__':
    tr, va, te = make_dataloaders()
    print('loaders:', len(tr.dataset), len(va.dataset), len(te.dataset))
