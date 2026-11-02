# 第 5 周 · PyTorch 入门（P1-B 上）

> **阶段**：P1-B PyTorch 基础（上）　|　**参考投入**：10-15h　|　**前置**：第 4 周（用 numpy 手写 2 层神经网络训练 MNIST 通关，懂前向/反向/梯度下降）
> **本周定位**：从 numpy 手写切换到 PyTorch。你会发现 `autograd` 自动帮你算了梯度、`nn.Module` 帮你组织了层、`DataLoader` 帮你批量喂数据——**框架只是把我第4周手写的那些自动化了**。

---

## 本周定位

第 4 周你用 numpy 手写了前向和反向传播。本周切换到 PyTorch，目标不是"又学一个工具"，而是**印证你第 4 周的理解**：PyTorch 的每一步都对应你手写过的东西。

- `autograd` 对应你手写的 `backward()`
- `nn.Linear` 对应你手写的 `W @ x + b`
- `optimizer.step()` 对应你手写的 `W -= lr * dW`
- `DataLoader` 对应你手写的 minibatch 切片

> 🔗 **本周 bad case 回看锚点（1h）**：P1-B 把 PaddleOCR 当成"训练好的模型"，去理解它的**输入预处理 / 输出后处理**。回想你 P0 跑 PaddleOCR 时，图片进模型前做了什么？（归一化、resize、转 tensor……）本周你写的 `DataLoader` 里的 `ToTensor()/除以255` 正是那个预处理步骤——这是"别人训好的模型"和你"自己训模型"之间最重要的那座桥。

## 本周目标

一句话：**用 PyTorch 的张量 / 自动求导 / nn.Module / DataLoader，从零搭一个 MLP 跑通 FashionMNIST 训练循环，画出 loss/acc 曲线，并能逐行讲清每个组件对应你第 4 周手写的哪一步。**

硬指标：
1. 能用 `torch.Tensor` 做基本运算，理解 `requires_grad` / `backward()` / `.grad`
2. 用 `nn.Module`（`nn.Linear` + `nn.Flatten` + 激活）搭一个 MLP
3. 用 `torchvision` 的 FashionMNIST + `DataLoader` 批量加载
4. 手写训练循环（forward → loss → backward → step），CPU 上跑通
5. 画出 loss / acc 曲线
6. **能讲清"autograd 替我做了第 4 周的哪部分"**（本周验收核心）

---

## 逐日安排

| 天 | 时长 | 任务 |
|---|---|---|
| Day 1（周一晚） | 1.5h | 跑 `b_env_check.py` 确认环境；读 PyTorch "Learn the Basics: Tensors" |
| Day 2（周二晚） | 1.5h | 写 `ex_pytorch_fundamentals.py` Part1：autograd 自动求梯度 |
| Day 3（周三晚） | 1.5h | 写 Part2：用 `nn.Module` 搭 MLP，前向出 `(B,10)` |
| Day 4（周四晚） | 1.5h | 写 `ex_train_loop.py`：DataLoader + 训练循环（先小数据 5000 张跑通） |
| Day 5（周五晚） | 1h | 上全量 FashionMNIST，看 loss 下降、acc 上升 |
| 周末（选一天） | 4-6h | 调通完整循环 + 画曲线 + 逐组件对照第 4 周 + bad case 回看 1h |

---

## 学什么 & 怎么学

### 模块 A · 环境与张量思维（Day 1）

**概念清单**：
- **深度学习框架在帮你做什么**：你第 4 周手写的"前向/反向/更新"三件事，框架全包了，你只管"描述网络长什么样 + 喂数据"。
- **张量（Tensor）= 带 GPU 能力的 numpy 数组**。图像就是 `H×W×C` 的 tensor，**别用表格思维**（P0 护栏第 2 条）。
- **NumPy 图像思维**：一张 28×28 灰度图是 `(28,28)`，彩色是 `(28,28,3)`；全连接网络要展平成 `(784,)`。

**动手**：
1. 直接运行脚手架验证环境（不学东西，但卡环境最浪费时间）：
   ```bash
   python b_env_check.py
   ```
   看到 PyTorch 版本 + "张量 matmul 自检通过" 即可。无 GPU 完全 OK。
2. 读 PyTorch 官方 "Learn the Basics: Tensors"：https://pytorch.org/tutorials/beginner/basics/tensor_tutorial.html

**产出**：环境 OK，建立"tensor = 数组"的直觉。

---

### 模块 B · Tensor 与自动求导 autograd（Day 2）⭐本周边界认知

**核心**：PyTorch 会在你做运算时**偷偷建一张计算图**，`backward()` 沿图自动链式求导——这就是你第 4 周手写的 `dZ2 = A2 - Y_oh`、`dW = A1.T @ dZ2` 那一套，**框架替你算**。

```python
import torch
x = torch.tensor(3.0, requires_grad=True)
y = x ** 2
y.backward()          # 反向传播
print(x.grad)         # 应等于 6.0（dy/dx = 2x = 6）
```

**动手**：写 `ex_pytorch_fundamentals.py` 的 Part1，分别实现标量版 `f(x)=x²` 和向量版 `z=sum(w*a)+b` 的自动求导，打印梯度并和手算核对。**重点体会：`requires_grad=True` 的 tensor，只要你碰了它，PyTorch 就记下怎么求导。**

**产出**：能解释 `requires_grad / backward() / .grad` 三者关系，并能说清"它替代了我第 4 周的哪段代码"。

---

### 模块 C · 用 nn.Module 搭网络（Day 3）

**概念清单**：
- **`nn.Module`**：所有网络层的基类，帮你管理参数（`parameters()`）、设备移动（`to(device)`）。
- **`nn.Linear(in, out)`**：就是 `y = x @ W^T + b`，对应你第 4 周的 `W2 @ A1 + b2`。
- **`nn.Flatten()`**：把 `(B,1,28,28)` 压成 `(B,784)`，连接"图像输入"和"全连接层"。

**动手**：写 `ex_pytorch_fundamentals.py` 的 Part2，用 `nn.Module` 搭一个 `784→128(ReLU)→10` 的 MLP，`forward` 接一个 batch 看输出是不是 `(B,10)`。顺手数一下参数量，对比第 4 周 numpy 版的 `784*128 + 128*10 + 偏置`。

**产出**：一个能前向出 `(B,10)` 的 MLP；参数量心里有数。

---

### 模块 D · DataLoader + 训练循环（Day 4-5）⭐本周动手核心

**核心**：把"数据批次"和"训练一步"交给框架，你的训练循环变短很多：

```python
for xb, yb in loader:                 # DataLoader 自动切片+打乱
    logits = model(xb)               # 前向（=你第4周 forward）
    loss = loss_fn(logits, yb)       # 交叉熵（nn.CrossEntropyLoss 已含 softmax）
    optimizer.zero_grad()            # 清空旧梯度
    loss.backward()                  # 反向（=你第4周 backward，但自动）
    optimizer.step()                 # 更新（=你第4周 W -= lr*dW，但自动）
```

**动手**：
1. 写 `ex_train_loop.py` 的 `TODO 2`：把 numpy 的 `(X,y)` 用 `TensorDataset` + `DataLoader` 包起来，`batch_size=128, shuffle=True`。
2. 写 `train_one_epoch` / `evaluate`（`TODO 3/4`）。**先取 5000 张小数据跑通**，确认 loss 下降、acc 上升，再上全量 60000。
3. 用 `data_utils.plot_curves` 画曲线，存到 `output/week5_curve.png`。

**产出**：FashionMNIST 训练循环跑通；loss 下降、acc 上升；曲线存盘。

---

### 周末 · 调通 + 对照讲解 + 回看（4-6h）

**1. 跑通完整循环**：上全量数据，看到 test_acc 稳步上升（本周不强求 >90%，第 6 周再冲里程碑）。

**2. 逐组件对照第 4 周**（验收核心，写进 `notes.md` 表格）：
| 第 4 周 numpy | 第 5 周 PyTorch |
|---|---|
| 手写 `forward()` | `model(xb)` |
| 手写 `backward()` 推梯度 | `loss.backward()`（autograd 自动） |
| 手写 `W -= lr*dW` | `optimizer.step()` |
| 手写 minibatch 切片 | `DataLoader` |

**3. bad case 回看（1h）**：翻 P0 的 `bad_cases/`，结合本周"输入预处理"话题，写几句话："PaddleOCR 对图片做了归一化/resize 才能进模型——我本周 DataLoader 的 `ToTensor()/÷255` 正是这一步；如果我的 bad case 是尺寸异常/未归一化导致的，根因就在这。"

**产出（= 本周成果）**：一个能跑通的 PyTorch MLP 训练脚本 + 曲线 + 组件对照表。

---

## 本周资源清单

| 用途 | 链接 |
|---|---|
| PyTorch 官方 "Learn the Basics"（Tensors/Autograd/Neural Nets/Optimization） | https://pytorch.org/tutorials/beginner/basics/intro.html |
| d2l 第 5 章 深度学习计算（层/块/参数管理/GPU） | https://zh.d2l.ai/chapter_deep-learning-computation/index.html |
| d2l 第 4 章 多层感知机（权重/过拟合铺垫） | https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html |
| 李沐视频（对应 d2l，B 站搜「跟李沐学AI 动手学深度学习」） | B 站搜「跟李沐学AI」 |
| FashionMNIST 数据集说明 | https://github.com/zalandoresearch/fashion-mnist |

> 若某个链接 404（版本变动），去 PyTorch 官网教程首页或 https://zh.d2l.ai/ 按章节名找。

---

## 验收清单（周末打勾）

- [ ] `b_env_check.py` 跑通，PyTorch 可用（有无 GPU 均可）
- [ ] Part1：autograd 标量/向量求导跑通，梯度与手算一致
- [ ] Part2：用 `nn.Module` 搭出 MLP，前向出 `(B,10)`，参数量说得出
- [ ] `ex_train_loop.py`：DataLoader + 训练循环跑通（先 5000 张后全量）
- [ ] 画出 loss / acc 曲线（存 `output/week5_curve.png`）
- [ ] **能逐组件讲清 PyTorch 对应第 4 周 numpy 的哪一步**（验收核心）
- [ ] 完成一次 bad case 回看并记录（聚焦"输入预处理"）

---

## 常见坑 & 卡住怎么办

- **`backward()` 报错"element 0 does not require grad"**：说明你操作的 tensor 没设 `requires_grad=True`，或用了 `.data` 切断了计算图。标量例子里 `x=torch.tensor(3.0, requires_grad=True)` 别忘了。
- **loss 不下降**：① 忘了 `optimizer.zero_grad()`（梯度累加导致乱更新）；② 学习率太小；③ 数据没归一化（FashionMNIST 要 `÷255`）。
- **形状对不上 `(B,1,28,28)` vs 模型期望 `(B,784)`**：在模型第一层加 `nn.Flatten()`，或在 DataLoader 里就展平。本周 `data_utils.load_fashion_mnist(flatten=True)` 已帮你展平。
- **`CrossEntropyLoss` 报错 shape**：它要求 `logits:(B,10)` + `label:(B,)` 的**整数类别**，不是 one-hot。别自己套 softmax+交叉熵，直接用 `nn.CrossEntropyLoss()`（内部含 softmax）。
- **"PyTorch 一行搞定，我第 4 周手写图啥"**：正因为你第 4 周手写过，本周才看得懂 `loss.backward()` 背后发生了什么——**理解深度天差地别**。第 6 周加正则/GPU/保存，你也会比"只调包"的人快得多。
- **卡住 >2h**：先看 PyTorch 官方 "Training with PyTorch" 教程，再回头读 d2l 第 5 章，别死磕推导。

---

## 进度日志（本周日填）

```
第 5 周（日期 ____）｜阶段 P1-B（上）
· 本周跑通了什么：____________________（PyTorch MLP 训练 FashionMNIST）
· 最终测试集准确率：____%（本周目标：看到上升即可）
· autograd 我能讲清"替代了第4周哪段"吗：能 / 还有 ____ 处模糊
· 肉眼看到了什么：____________________（loss 下降 / acc 上升曲线）
· bad case 回看的新理解（输入预处理）：____________
· 卡在哪、怎么解决的：________________
· 下周（P1-B 下 · 正则化/GPU/保存 + 里程碑）第一件事：____________
```
