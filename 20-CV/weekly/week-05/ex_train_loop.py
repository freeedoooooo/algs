"""
第5周练习② · DataLoader + PyTorch 训练循环（自己填！）

⚠️ 学习规则：
    1. 训练循环必须自己写，对照你第4周 numpy 的 train()，理解 PyTorch 如何"自动化"了它。
    2. 卡住超过 2 小时：看 PyTorch "Learn the Basics: Training with PyTorch" + d2l 第4/5章。
    3. 目标：FashionMNIST 上跑通，看到 loss 下降、acc 上升。
       （本周不强求 >90%，那是第6周的里程碑。）

参考：https://pytorch.org/tutorials/beginner/basics/optimization_tutorial.html
"""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from data_utils import load_fashion_mnist, plot_curves

X_train, y_train, X_test, y_test = load_fashion_mnist(flatten=True)


# TODO 1: 定义一个 MLP（可直接复用练习①的 MLP，这里重写一份也行）
class MLP(nn.Module):
    def __init__(self, n_in=784, n_hid=128, n_out=10):
        super().__init__()
        self.flatten = nn.Flatten()
        # TODO 1.1: 定义 fc1 = nn.Linear(n_in, n_hid)，激活 ReLU，fc2 = nn.Linear(n_hid, n_out)
        self.fc1 = None
        self.relu = nn.ReLU()
        self.fc2 = None
        raise NotImplementedError

    def forward(self, x):
        # TODO 1.2: flatten → fc1 → relu → fc2，返回 logits (B,10)
        raise NotImplementedError


# TODO 2: 把 numpy 数据包装成 TensorDataset + DataLoader
# from torch.utils.data import TensorDataset
# train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
# train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)


def train_one_epoch(model, loader, loss_fn, optimizer, device):
    """训练一个 epoch。返回 (平均 loss, 准确率)。"""
    model.train()
    total_loss, n_correct, n = 0.0, 0, 0
    for xb, yb in loader:
        # TODO 3a: xb/yb 送 device；前向得到 logits
        # TODO 3b: 算 loss = loss_fn(logits, yb)
        # TODO 3c: optimizer.zero_grad() → loss.backward() → optimizer.step()
        # TODO 3d: 累计 loss 和 正确预测数（logits.argmax(1) == yb）
        raise NotImplementedError
    return total_loss / max(len(loader), 1), n_correct / max(n, 1)


@torch.no_grad()
def evaluate(model, X, y, loss_fn, device, batch_size=256):
    """在给定数据上算 (loss, 准确率)。"""
    model.eval()
    # TODO 4: 用 TensorDataset+DataLoader 或直接矩阵运算逐 batch 算
    #   累计 loss 与正确数，最后返回平均。注意用 model.eval() + no_grad 关掉 dropout/batchnorm 统计
    raise NotImplementedError


if __name__ == '__main__':
    device = 'cpu'                      # 本周用 CPU 即可
    model = MLP().to(device)
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

    # 建议先取 5000 张小数据跑通，确认 loss 下降，再上全量 60000
    losses, accs = [], []
    for ep in range(5):
        # tr_loss = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        # te_acc  = evaluate(model, X_test, y_test, loss_fn, device)
        # losses.append(tr_loss); accs.append(te_acc)
        # print(f'epoch {ep}  loss={tr_loss:.4f}  test_acc={te_acc:.3f}')
        raise NotImplementedError

    plot_curves(losses, accs, save='output/week5_curve.png')
    print('最终测试集准确率（目标：本周看到明显上升即可，>90% 是第6周里程碑）：', accs[-1] if accs else None)
