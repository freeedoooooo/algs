"""
第7周脚手架 · 卷积可视化（直接运行）

用真实灰度图 + 边缘检测核（Sobel），直观感受"卷积 = 特征提取"：
一个小小的 3x3 核，就能从一张鞋/包的照片里抽出轮廓边缘。

手写卷积是 ex_conv2d.py 的事；这里用 scipy 跑同样的效果做"眼见为实"演示，
帮你建立"卷积核在提取什么"的直觉（也可换成你自己的核试试）。
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import convolve2d

from data_utils import load_sample_image

img = load_sample_image()                 # (H, W) 0-1 灰度图

# Sobel 边缘检测核（横/纵方向）
sobel_x = np.array([[-1, 0, 1],
                    [-2, 0, 2],
                   [-1, 0, 1]], dtype=float)
sobel_y = sobel_x.T

edge_x = convolve2d(img, sobel_x, mode='same', boundary='symm')
edge_y = convolve2d(img, sobel_y, mode='same', boundary='symm')
edge = np.sqrt(edge_x**2 + edge_y**2)

fig, axes = plt.subplots(1, 3, figsize=(12, 4))
axes[0].imshow(img, cmap='gray');      axes[0].set_title('原图')
axes[1].imshow(np.abs(edge), cmap='gray'); axes[1].set_title('Sobel 边缘（卷积提取）')
axes[2].imshow(np.abs(edge_x), cmap='gray'); axes[2].set_title('横向梯度')
for a in axes:
    a.axis('off')
plt.tight_layout()
import os
os.makedirs('output', exist_ok=True)
plt.savefig('output/conv_edge_demo.png')
print('已存 output/conv_edge_demo.png —— 再看一眼：卷积核就是"特征探测器"')
