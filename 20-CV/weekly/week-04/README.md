# 第 4 周 · 手写神经网络（P1-A 里程碑）

> **阶段**：P1-A 深度学习地基（下半 / 收尾）　|　**参考投入**：10-15h　|　**前置**：第 3 周（会 numpy 线性/softmax 回归、懂反向传播概念）
> **本周产出 P1-A 的里程碑**：用纯 numpy 手写一个 2 层神经网络训练 MNIST，能解释反向传播每一步在算什么。

---

## 本周定位

第 3 周你写的都是"单层"模型（线性回归、softmax 回归）。本周要**加一层隐藏层 + 激活函数**，变成真正的"神经网络"，并亲手实现它的反向传播。这是 P1-A 的**毕业作品**——完成后你就彻底理解了"神经网络怎么学"，之后 P1-B 用 PyTorch 时会发现"框架只是把我手写的这些自动化了"。**手写一次，受益整个 P1。**

> 🔗 **本周 bad case 回看锚点（1h）**：你现在懂了"隐藏层 + 非线性激活让网络能拟合复杂模式"。回想 OCR：为什么识别"8"和"B"这种形近字符需要深层网络而不是单层？把想法记进日志。

## 本周目标

一句话：**纯 numpy 手写一个含隐藏层的神经网络，训练 MNIST 手写数字分类，准确率 ≥95%，并能逐行解释反向传播。**

硬指标：
1. 实现一个 `输入层(784) → 隐藏层(如128) → 输出层(10)` 的 2 层网络
2. 用 ReLU（隐藏层）+ softmax（输出层）+ 交叉熵损失
3. 手写完整反向传播（两个线性层 + 激活的梯度）
4. 在 MNIST 上训练，测试准确率 **≥95%**
5. 画出 loss / accuracy 曲线
6. **能对着代码逐行讲清"每一步在算什么"**（这是验收核心）

---

## 逐日安排

| 天 | 时长 | 任务 |
|---|---|---|
| Day 1（周一晚） | 1.5h | 学多层感知机(MLP)结构 + ReLU；下载 MNIST 数据并看懂形状 |
| Day 2（周二晚） | 1.5h | 写前向传播（两层 + 激活 + softmax） |
| Day 3（周三晚） | 1.5h | 写反向传播（重点难点，逐层推梯度） |
| Day 4（周四晚） | 1.5h | 组装训练循环（minibatch + 更新参数），先跑通小规模 |
| Day 5（周五晚） | 1h | 跑完整 MNIST 训练，调学习率/隐藏层大小 |
| 周末（选一天） | 4-6h | 达标记（≥95%）+ 画曲线 + 逐行讲解反向传播 + bad case 回看 |

---

## 学什么 & 怎么学

### 模块 A · MLP 结构 + 数据准备（Day 1）

**概念清单**：
- **多层感知机（MLP）**：在线性层之间插入"隐藏层 + 非线性激活"，让网络能拟合非线性关系。**没有激活函数，多层线性叠加还是等价于单层**——这是必须理解的点。
- **ReLU**：`f(x)=max(0,x)`，最常用的隐藏层激活，简单且缓解梯度消失。
- **MNIST**：手写数字数据集，每张 28×28 灰度图，标签 0-9。**要展平成 784 维向量**喂给全连接网络。

**怎么学 / 动手**：
1. 读 d2l 第 4 章（多层感知机）4.1-4.3：https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html
2. 下载 MNIST。最省事的方式（用 torchvision 只当"数据下载器"，模型仍手写）：
   ```python
   from torchvision import datasets, transforms
   import numpy as np

   tf = transforms.Compose([transforms.ToTensor()])
   train = datasets.MNIST(root='./data', train=True, download=True, transform=tf)
   test  = datasets.MNIST(root='./data', train=False, download=True, transform=tf)

   # 转成 numpy，展平 28*28=784
   X_train = train.data.numpy().reshape(-1, 784).astype('float32') / 255.0
   y_train = train.targets.numpy()
   X_test  = test.data.numpy().reshape(-1, 784).astype('float32') / 255.0
   y_test  = test.targets.numpy()
   print(X_train.shape, y_train.shape)   # (60000, 784) (60000,)
   ```
3. 看清形状：`X` 是 `(样本数, 784)`，`y` 是 `(样本数,)` 的 0-9 整数。

**产出**：MNIST 下载好，X/y 形状搞清楚。

---

### 模块 B · 前向传播（Day 2）

**网络结构**：`784 → 128(隐藏层, ReLU) → 10(输出层, softmax)`

```python
import numpy as np

def relu(z):
    return np.maximum(0, z)

def softmax(z):
    z = z - z.max(axis=1, keepdims=True)     # 数值稳定
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)

def one_hot(y, num_cls=10):
    N = len(y)
    oh = np.zeros((N, num_cls))
    oh[np.arange(N), y] = 1
    return oh

# 初始化参数（He 初始化，配 ReLU）
np.random.seed(0)
n_in, n_hid, n_out = 784, 128, 10
W1 = np.random.randn(n_in, n_hid) * np.sqrt(2.0 / n_in)
b1 = np.zeros((1, n_hid))
W2 = np.random.randn(n_hid, n_out) * np.sqrt(2.0 / n_out)
b2 = np.zeros((1, n_out))

def forward(X):
    Z1 = X @ W1 + b1          # 第一层线性
    A1 = relu(Z1)             # 隐藏层激活
    Z2 = A1 @ W2 + b2         # 第二层线性
    A2 = softmax(Z2)          # 输出概率
    return Z1, A1, Z2, A2
```

**要理解**：数据怎么一层层从 784 维变成 10 个类别概率；每一层的 shape 变化（`X@W1`: (N,784)@(784,128)=(N,128)）。

**产出**：`forward()` 能跑，输出 `A2` 是 `(N,10)` 的概率（每行和为 1）。

---

### 模块 C · 反向传播（Day 3）⭐本周最难，重点投入

**核心思想**：从损失出发，用**链式法则**逐层往回算每个参数的梯度。对"softmax + 交叉熵"这个组合，输出层梯度有一个**极其简洁的结论**：`dZ2 = A2 - Y_onehot`。

```python
def cross_entropy(probs, Y_oh):
    N = len(probs)
    return -np.sum(Y_oh * np.log(probs + 1e-12)) / N

def backward(X, Y_oh, Z1, A1, Z2, A2):
    N = len(X)
    # 输出层：softmax+交叉熵的梯度 = 预测概率 - 真实标签（记住这个经典结论）
    dZ2 = (A2 - Y_oh) / N                 # (N,10)
    dW2 = A1.T @ dZ2                      # (128,10)
    db2 = dZ2.sum(axis=0, keepdims=True)

    # 传回隐藏层
    dA1 = dZ2 @ W2.T                      # (N,128)
    dZ1 = dA1 * (Z1 > 0)                  # ReLU 的导数：>0处为1，否则为0
    dW1 = X.T @ dZ1                       # (784,128)
    db1 = dZ1.sum(axis=0, keepdims=True)
    return dW1, db1, dW2, db2
```

**逐行要能讲清**（这是验收核心）：
- `dZ2 = A2 - Y_oh`：为什么 softmax+交叉熵求导后这么干净？（因为指数和对数抵消）
- `dW2 = A1.T @ dZ2`：权重梯度 = 上一层激活的转置 @ 本层输入梯度
- `dZ1 = dA1 * (Z1>0)`：ReLU 的导数——正区间导数为 1，负区间为 0
- 每个梯度的 shape 是否和对应参数一致（`dW2` 必须是 `(128,10)`）

> **卡住就看 d2l 4.8（反向传播）+ 3B1B 第 3-4 集**回炉。先照抄跑通，再逐行懂——**top-down，别死磕推导。**

**产出**：`backward()` 能算出 4 个梯度，shape 全部对得上，且你能逐行解释。

---

### 模块 D · 训练循环 + minibatch（Day 4）

**为什么要 minibatch**：一次只用一小批数据更新，比全量快、比单样本稳。

```python
def train(X, y, epochs=5, batch_size=128, lr=0.1):
    global W1, b1, W2, b2
    Y_oh_full = one_hot(y)
    N = len(X)
    losses, accs = [], []
    for ep in range(epochs):
        idx = np.random.permutation(N)          # 每轮打乱
        for i in range(0, N, batch_size):
            batch = idx[i:i+batch_size]
            Xb, Yb = X[batch], Y_oh_full[batch]
            Z1, A1, Z2, A2 = forward(Xb)
            dW1, db1, dW2, db2 = backward(Xb, Yb, Z1, A1, Z2, A2)
            # 梯度下降更新
            W1 -= lr*dW1; b1 -= lr*db1
            W2 -= lr*dW2; b2 -= lr*db2
        # 每轮末评估（用全量训练集看趋势，最终达标以测试集为准）
        _, _, _, A2 = forward(X)
        loss = cross_entropy(A2, Y_oh_full)
        acc = (A2.argmax(axis=1) == y).mean()
        losses.append(loss); accs.append(acc)
        print(f'epoch {ep}  loss={loss:.4f}  acc={acc:.3f}')
    return losses, accs
```

**动手**：
1. 先用**小数据**（如取 5000 张）跑通，确认 loss 下降、acc 上升。
2. 再上全量 60000 张训练。

**产出**：训练循环跑通，能看到 loss 下降、准确率上升。

---

### 周末 · 达标记 + 讲解 + 回看（4-6h）

**1. 调到 ≥95%**：
- 隐藏层太小（如 32）可能不够，试 `128` 或 `256`
- 学习率 `0.1` 起步，发散就调小
- 训练 `5-10` 个 epoch 一般能到 95%+
- 用 `X_test/y_test` 评估测试集准确率（**别只看训练集，那是过拟合陷阱**）

**2. 画曲线**：loss 下降 + accuracy 上升两条曲线（matplotlib）。

**3. 逐行讲解反向传播**：对着 `backward()`，把每一行"在算什么"写成注释或讲给自己听。**这是 P1-A 的验收核心——能讲清才算真懂。**

**4. bad case 回看（1h）**：结合"隐藏层+非线性让网络能拟合复杂模式"，回想为什么形近字符识别需要深层网络。记进日志。

**产出（= P1-A 里程碑）**：一个 ≥95% 的 numpy 手写神经网络 + loss/acc 曲线 + 能逐行讲反向传播。

---

## 本周资源清单

| 用途 | 链接 |
|---|---|
| d2l 第 4 章 多层感知机 | https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html |
| d2l 4.8 反向传播 | 见第 4 章内 |
| 3B1B 神经网络第 3-4 集（反向传播） | https://www.3blue1brown.com/topics/neural-networks |
| MNIST（用 torchvision 下载） | https://pytorch.org/vision/stable/ |
| 鱼书《深度学习入门》（numpy 手写神书，可选参考） | 图书馆/电商搜"深度学习入门 斋藤康毅" |

> **强烈推荐**：若手写反向传播卡壳，斋藤康毅《深度学习入门：基于 Python 的理论与实现》（俗称"鱼书"）第 5 章用 numpy 从零搭建神经网络，讲得极清楚，是本周的最佳辅助。

---

## 验收清单（周末打勾）

- [ ] 实现了 `784→128→10` 的 2 层网络（ReLU + softmax + 交叉熵）
- [ ] 手写反向传播，4 个梯度 shape 全对
- [ ] MNIST 测试集准确率 **≥95%**
- [ ] 画了 loss / accuracy 曲线
- [ ] **能对着 backward() 逐行讲清每步在算什么**（P1-A 验收核心）
- [ ] 用测试集（而非训练集）评估，理解过拟合陷阱
- [ ] 完成一次 bad case 回看

---

## 常见坑 & 卡住怎么办

- **反向传播推不出来**：**先照抄本周代码跑通**（top-down），看到 loss 下降后再对着 d2l 4.8 / 鱼书第 5 章逐行懂。别死磕公式。
- **准确率卡在 10%（等于瞎猜）**：多半是梯度算错或没更新。检查：①`dZ2 = A2 - Y_oh` 符号 ②学习率是否太小 ③参数是否真的被 `global` 更新了。
- **loss 变 NaN**：学习率太大，调到 `0.01`；或 softmax 没减最大值导致溢出。
- **训练集 99% 但测试集 90%**：过拟合。本周达标即可，正则化（dropout/权重衰减）P1-B 学。
- **shape 对不上报错**：拿张纸画出每层的 `(行,列)`，矩阵乘法 `(N,a)@(a,b)=(N,b)`，一个个核对。这是理解矩阵乘法最好的练习。
- **觉得"手写这个有什么用，PyTorch 一行搞定"**：正因为下周（P1-B）用 PyTorch，你现在手写一次，下周就会恍然大悟"autograd 自动帮我做了 backward"——**理解深度天差地别。这一周是 P1 最值的投入。**

---

## 进度日志（本周日填）

```
第 4 周（日期 ____）｜阶段 P1-A（下 · 里程碑）
· 本周跑通了什么：____________________（手写神经网络训练 MNIST）
· 测试集准确率：____%（目标 ≥95%）
· 反向传播我能逐行讲清吗：能 / 还有 ____ 处模糊
· 肉眼看到了什么：____________________（loss 下降 / acc 上升曲线）
· bad case 回看的新理解：____________
· 卡在哪、怎么解决的：________________
· ✅ P1-A 是否通关：____________
· 下周（P1-B PyTorch）第一件事：____________
```
