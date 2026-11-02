"""
第7周练习① · 用 numpy 手写卷积 & 池化（自己填！）

⚠️ 学习规则：
    1. 卷积/池化的前向必须自己写——这是理解 CNN 的唯一捷径，看十遍不如写一遍并核对 shape。
    2. 卡住超过 2 小时：看 d2l 第 6 章(卷积) + 玩 CNN Explainer。
    3. 目标：单通道卷积、最大池化、多通道卷积都能手写，并核对输出 shape。

重要公式（务必自己算一遍）：
    out_h = floor((in_h + 2*padding - kernel_h) / stride) + 1
    （宽同理；本练习 kernel 用方阵，故 kh=kw）
"""
import numpy as np


def conv2d_single(x, k, stride=1, padding=0):
    """单通道 2D 卷积。
    x: (H, W)        输入
    k: (kh, kw)      卷积核（本函数 kh==kw）
    返回: (out_h, out_w)
    """
    # TODO 1.1: 对 x 四周补零 padding（用 np.pad，mode='constant'）
    # TODO 1.2: 用上面的尺寸公式确定 out_h, out_w
    # TODO 1.3: 滑窗，逐位置算 sum(x_window * k)；注意步长 stride
    raise NotImplementedError


def max_pool2d(x, pool=2, stride=2):
    """最大池化。x: (H, W) → (H//pool, W//pool)。
    取每个 pool×pool 窗口的最大值，降低分辨率、保留显著特征。
    """
    # TODO 2: 滑窗取最大值（步长默认等于窗口大小）
    raise NotImplementedError


def conv2d_multi(x, kernels, biases=None):
    """多通道卷积。
    x:       (C_in, H, W)
    kernels: (C_out, C_in, kh, kw)   每个输出通道对应一组(C_in 个)核
    biases:  (C_out,) 或 None
    返回: (C_out, out_h, out_w)
    """
    C_in, H, W = x.shape
    C_out = kernels.shape[0]
    # TODO 3.1: 对每一个输出通道 c_out：
    #     把 x 的每个输入通道 c_in 与 kernels[c_out, c_in] 卷积，逐通道相加，再加 biases[c_out]
    # TODO 3.2: 核对 shape：输出通道数 = C_out，空间尺寸由单通道卷积公式决定
    raise NotImplementedError


if __name__ == '__main__':
    # ---- 单通道自检 ----
    x = np.array([[1, 2, 3],
                  [4, 5, 6],
                  [7, 8, 9]], dtype=float)
    k = np.array([[1, 0],
                  [0, 1]], dtype=float)
    # 手算：无 padding、stride=1 时，2x2 核在 3x3 上滑动，输出应为 2x2 = [[6,8],[12,14]]
    out = conv2d_single(x, k, stride=1, padding=0)
    print('conv single out（应为 2x2=[[6,8],[12,14]]）:\n', out)

    # ---- 池化自检 ----
    p = max_pool2d(x, pool=2, stride=2)
    print('max pool 2x2（应为 [[5,6],[8,9]]）:\n', p)

    # ---- 多通道自检 ----
    x3 = np.random.randn(3, 8, 8)            # 3 通道 8x8
    ks = np.random.randn(3, 3, 3, 3)         # 3 输出通道，每个含 3 个 3x3 核
    out3 = conv2d_multi(x3, ks)
    print('multi out shape（应为 (3, 6, 6)）:', out3.shape)   # 8-3+1 = 6
