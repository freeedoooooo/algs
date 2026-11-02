"""
第8周练习 · 用 PyTorch 搭 CNN 并训练（自己填！）

⚠️ 学习规则：
    1. 用 nn.Conv2d / nn.MaxPool2d / nn.Flatten 搭一个小型 CNN（LeNet 风格）。
       卷积的"滑窗加权求和"你第7周已手写过——本周只是换成框架实现。
    2. 卡住超过 2 小时：看 d2l 第 6 章 + CNN Explainer。
    3. 里程碑：① 能口头解释"卷积在做什么 / 感受野 / 为什么 CNN 适合图像"；
       ② 同 FashionMNIST 上，本周 CNN 应明显好于你第6周的 MLP（更高/更快收敛）。

输入：FashionMNIST 图像 (B, 1, 28, 28)（注意：不展平，保留空间结构）。
"""
import torch
import torch.nn as nn
from data_utils import make_cnn_dataloaders, plot_curves

train_loader, test_loader = make_cnn_dataloaders()


class LeNet(nn.Module):
    def __init__(self, n_out=10):
        super().__init__()
        # TODO 1: 卷积块1 —— Conv2d(1, 6, kernel_size=5) → ReLU → MaxPool2d(2)
        # TODO 2: 卷积块2 —— Conv2d(6, 16, kernel_size=5) → ReLU → MaxPool2d(2)
        #   提示：28x28 经过两次 5x5 卷积 + 2x2 池化后，特征图约变成 4x4，通道 16
        #   （自己推一下 28→24→12→8→4 的逐层尺寸）
        # TODO 3: 展平 → 两个全连接 (16*4*4=256 → 120 → 84) 中间 ReLU → 输出 (84 → n_out)
        self.conv1 = None
        self.pool = None
        self.conv2 = None
        self.fc1 = None
        self.fc2 = None
        self.fc3 = None
        raise NotImplementedError

    def forward(self, x):
        # TODO 4: x: (B,1,28,28) → 卷积块1 → 池化 → 卷积块2 → 池化
        #   → Flatten → fc1 → ReLU → fc2 → ReLU → fc3
        #   返回 logits (B, n_out)
        raise NotImplementedError


def train_one_epoch(model, loader, loss_fn, optimizer, device):
    model.train()
    total_loss, n_correct, n = 0.0, 0, 0
    for xb, yb in loader:
        # TODO 5: xb/yb 送 device；前向→loss→zero_grad→backward→step；累计 loss/正确数
        raise NotImplementedError
    return total_loss / max(len(loader), 1), n_correct / max(n, 1)


@torch.no_grad()
def evaluate(model, loader, loss_fn, device):
    model.eval()
    # TODO 6: 在 loader 上算 (loss, 准确率)
    raise NotImplementedError


if __name__ == '__main__':
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = LeNet().to(device)
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

    losses, accs = [], []
    for ep in range(10):
        # tr_loss = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        # te_acc  = evaluate(model, test_loader, loss_fn, device)[1]
        # losses.append(tr_loss); accs.append(te_acc)
        # print(f'epoch {ep}  loss={tr_loss:.4f}  test_acc={te_acc:.3f}')
        raise NotImplementedError

    plot_curves(losses, accs, save='output/week8_curve.png')
    # 对比：你第6周 MLP 的测试准确率（应 < 本周 CNN）。
    # 达标后：对着 notes.md 把"卷积/感受野/为什么 CNN 适合图像"三句话写顺，这是 P1-C 验收核心。
