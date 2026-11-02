"""
第7周脚手架 · 样例图加载 / 画图（可直接运行/导入）

boilerplate：从 FashionMNIST 抽一张灰度图给你做卷积可视化演示，以及通用画图。
手写卷积才是本周学习重点（见 ex_conv2d.py），这些替你写好。
"""
import numpy as np
import matplotlib.pyplot as plt


def load_sample_image(data_root='./data', idx=0):
    """从 FashionMNIST 抽一张图，返回 (H, W) 的 0-1 float 灰度图。"""
    from torchvision import datasets, transforms
    tf = transforms.Compose([transforms.ToTensor()])
    ds = datasets.FashionMNIST(root=data_root, train=True, download=True, transform=tf)
    img = ds.data[idx].numpy().astype('float32') / 255.0
    return img


def show_image(img, title='image', save=None):
    plt.figure(figsize=(4, 4))
    plt.imshow(img, cmap='gray')
    plt.title(title)
    plt.axis('off')
    if save:
        import os
        os.makedirs(os.path.dirname(save) or '.', exist_ok=True)
        plt.savefig(save)
        print(f'已存 {save}')


if __name__ == '__main__':
    img = load_sample_image()
    print('样例图形状:', img.shape, '取值区间:', img.min(), img.max())
    show_image(img, title='sample', save='output/sample.png')
