"""
第5周练习① · PyTorch 张量 / 自动求导 / nn.Module（自己填！）

⚠️ 学习规则（本周最重要，请遵守）：
    1. 下面带 TODO 的函数必须自己写，一个字都别抄 README——README 里只给思路提示。
    2. 先跑通 Part1（autograd 自动求梯度），再写 Part2（nn.Module 搭 MLP）。
       top-down：先看到结果，再回头懂原理。
    3. 卡住超过 2 小时：看 PyTorch 官方 "Learn the Basics" + d2l 第5章（深度学习计算）。
    4. 关键对照：你第4周用 numpy 手写了 backward()。本周 autograd 帮你自动做了那一步——
       能讲清"对应哪一步"才算真懂。

参考：PyTorch 官方教程 https://pytorch.org/tutorials/beginner/basics/intro.html
"""
import torch
import torch.nn as nn


# ============ Part 1：Tensor 与自动求导 ============
def demo_autograd_scalar():
    """标量情形：求 f(x)=x^2 在 x=3 处的导数（手算应为 6）。"""
    x = torch.tensor(3.0, requires_grad=True)
    # TODO 1.1: 定义 y = x ** 2
    y = None
    # TODO 1.2: 反向传播，计算梯度
    # y.backward()
    # TODO 1.3: 打印 x.grad，应等于 6.0
    print('dy/dx at x=3:', x.grad)
    return x.grad


def demo_autograd_vector():
    """向量情形：z = sum(w * a) + b，对 w 和 a 求梯度。"""
    a = torch.randn(4, requires_grad=True)
    w = torch.randn(4, requires_grad=True)
    b = torch.randn(1, requires_grad=True)
    # TODO 1.4: z = (w * a).sum() + b
    z = None
    # z.backward()
    # 想一想：dz/dw 应该等于 a，dz/da 应该等于 w（打印验证）
    print('dz/dw (=a?):', w.grad)
    print('dz/da (=w?):', a.grad)
    return w.grad, a.grad


# ============ Part 2：用 nn.Module 搭 MLP ============
class MLP(nn.Module):
    def __init__(self, n_in=784, n_hid=128, n_out=10):
        super().__init__()
        # TODO 2.1: 搭网络 输入(n_in) → 展平 → Linear(n_in,n_hid) → ReLU → Linear(n_hid,n_out)
        # 提示：若输入是 (B,1,28,28)，先用 nn.Flatten() 展平成 (B,784)。
        # 可以用 nn.Sequential 一次写完，也可以逐层定义后写在 forward 里。
        self.net = None
        raise NotImplementedError

    def forward(self, x):
        # TODO 2.2: 把 x 送入 self.net，返回 logits，shape 应为 (B, n_out)
        raise NotImplementedError


if __name__ == '__main__':
    # ---- Part1 自检 ----
    print('=== Part1: autograd ===')
    demo_autograd_scalar()
    demo_autograd_vector()

    # ---- Part2 自检 ----
    print('=== Part2: nn.Module MLP ===')
    model = MLP()
    xb = torch.randn(4, 1, 28, 28)        # 一个 batch：4 张 1x28x28 图像
    out = model(xb)
    print('输出 shape（应为 (4,10)）:', tuple(out.shape))
    n_params = sum(p.numel() for p in model.parameters())
    print('总参数量:', n_params, '（对比第4周 numpy 的 784*128 + 128*10 + 偏置）')
