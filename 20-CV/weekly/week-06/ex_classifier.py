"""
第6周练习 · 完整分类 pipeline + 里程碑（自己填！）

⚠️ 学习规则：
    1. 在巩固第5周训练循环基础上，自己加：dropout / 权重衰减 / GPU / 模型保存。
    2. 卡住超过 2 小时：看 d2l 第4章(权重衰减/dropout) + PyTorch 官方文档。
    3. 里程碑：FashionMNIST 测试集 >90%，画出 train/val 曲线并解释。

本周"新东西"（都是你来写，不是 boilerplate）：
  · nn.Dropout：加在哪、为什么能缓解过拟合（训练时随机丢弃，测试时关闭）
  · optimizer 的 weight_decay（= L2 正则，你第4周在损失里见过）
  · 模型/数据 .to(device) 把计算搬上 GPU（有则加速，无则仍用 CPU）
  · torch.save(model.state_dict(), ...) / load_state_dict(...) 保存后再载入复用
"""
import torch
import torch.nn as nn
from data_utils import make_dataloaders, plot_curves, save_model, load_model

train_loader, val_loader, test_loader = make_dataloaders()


class MLP(nn.Module):
    def __init__(self, n_in=784, n_hid=128, n_out=10, dropout=0.2):
        super().__init__()
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(n_in, n_hid)
        self.relu = nn.ReLU()
        # TODO 1: 加一个 nn.Dropout(dropout)。想想放在激活之后还是之前更合理？
        self.drop = None
        self.fc2 = nn.Linear(n_hid, n_out)

    def forward(self, x):
        x = self.flatten(x)
        x = self.relu(self.fc1(x))
        # TODO 2: 过 dropout 层
        x = self.fc2(x)
        return x


device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = MLP(dropout=0.2).to(device)
loss_fn = nn.CrossEntropyLoss()

# TODO 3: 在优化器里加 weight_decay=1e-4（这就是 L2 正则，抑制大权重）
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)   # ← 改这一行，加 weight_decay=


def train_one_epoch(model, loader, loss_fn, optimizer, device):
    model.train()
    total_loss, n_correct, n = 0.0, 0, 0
    for xb, yb in loader:
        # TODO 4: xb/yb 送 device；前向→loss→zero_grad→backward→step
        # 累计 loss 与正确数（logits.argmax(1)==yb）
        raise NotImplementedError
    return total_loss / max(len(loader), 1), n_correct / max(n, 1)


@torch.no_grad()
def evaluate(model, loader, loss_fn, device):
    model.eval()
    # TODO 5: 在 loader 上算 (loss, 准确率)
    raise NotImplementedError


if __name__ == '__main__':
    best_acc = 0.0
    losses, val_accs = [], []
    for ep in range(10):
        # tr_loss = train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        # va_acc  = evaluate(model, val_loader, loss_fn, device)[1]
        # losses.append(tr_loss); val_accs.append(va_acc)
        # print(f'epoch {ep}  loss={tr_loss:.4f}  val_acc={va_acc:.3f}')
        # TODO 6: 若 val_acc 创新高，save_model(model) 存下"最佳模型"
        raise NotImplementedError

    # TODO 7: 训练结束后，用 load_model 把最佳模型载入，在 test_loader 上评估
    #   目标：测试集 >90%。对比"去掉 dropout/weight_decay"时 val 是否更早变差。
    # final_acc = evaluate(model, test_loader, loss_fn, device)[1]
    # print('测试集准确率（里程碑，目标 >90%）:', final_acc)
    plot_curves(losses, val_accs, save='output/week6_curve.png')
