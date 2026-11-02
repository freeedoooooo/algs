"""
第8周脚手架 · 第一层卷积核 & 特征图可视化（直接运行）

帮你"看见" CNN 学到了什么：
  1) 第一层卷积核（权重）——它们长什么样（边缘？斑点？）
  2) 拿一张输入图喂进网络，看第一层卷积输出的特征图

搭网络（ex_cnn.py）是你本周学习重点；这里只是把训好的/随机初始化的权重画出来，
帮你在"数学"和"直觉"之间架桥。可在你训练完 LeNet 后 import 复用。
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn

from data_utils import make_cnn_dataloaders, load_fashion_mnist_image


def build_lenet_for_viz():
    """和 ex_cnn.py 同结构的 LeNet，仅用于可视化（权重可随机或加载你训好的）。"""
    model = nn.Sequential(
        nn.Conv2d(1, 6, 5), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(6, 16, 5), nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(16 * 4 * 4, 120), nn.ReLU(),
        nn.Linear(120, 84), nn.ReLU(),
        nn.Linear(84, 10),
    )
    return model


def visualize_kernels(model, save='output/week8_kernels.png'):
    """画第一层卷积核（6 个 5x5）。"""
    conv1 = model[0] if isinstance(model, nn.Sequential) else model.conv1
    kernels = conv1.weight.detach().cpu().numpy()      # (6,1,5,5)
    fig, axes = plt.subplots(1, 6, figsize=(12, 2.5))
    for i in range(6):
        axes[i].imshow(kernels[i, 0], cmap='RdBu_r', vmin=-0.5, vmax=0.5)
        axes[i].set_title(f'kernel {i}')
        axes[i].axis('off')
    plt.tight_layout()
    os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
    plt.savefig(save)
    print(f'第一层卷积核已存 {save}')


def visualize_feature_maps(model, save='output/week8_featuremaps.png'):
    """拿一张图过第一层卷积，画 6 个特征图。"""
    X_train, _, _, _ = load_fashion_mnist_image()
    img = torch.from_numpy(X_train[:1])                 # (1,1,28,28)
    with torch.no_grad():
        feats = model[0](img) if isinstance(model, nn.Sequential) else model.conv1(img)
    feats = feats[0].cpu().numpy()                      # (6, h, w)
    fig, axes = plt.subplots(1, 6, figsize=(12, 3))
    for i in range(6):
        axes[i].imshow(feats[i], cmap='viridis')
        axes[i].set_title(f'feature {i}')
        axes[i].axis('off')
    plt.tight_layout()
    os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
    plt.savefig(save)
    print(f'第一层特征图已存 {save}')


if __name__ == '__main__':
    model = build_lenet_for_viz()
    visualize_kernels(model)
    visualize_feature_maps(model)
    print('（提示：用你自己 ex_cnn.py 训好的 LeNet 替换 model，看到的核会更有"语义"。）')
