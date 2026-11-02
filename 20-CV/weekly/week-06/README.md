# 第 6 周 · 完整训练 pipeline + 里程碑（P1-B 下）

> **阶段**：P1-B PyTorch 基础（下）　|　**参考投入**：10-15h　|　**前置**：第 5 周（会用 autograd/nn.Module/DataLoader 跑通 MLP 训练循环）
> **本周里程碑**：用 PyTorch 从零写出完整训练 pipeline，FashionMNIST 测试集 **>90%**，能画出 loss/acc 曲线并解释。

---

## 本周定位

第 5 周你跑通了"能训练"的循环。本周把它** hardening（加固）成生产可用的 pipeline**：加 dropout/权重衰减防过拟合、用 GPU 加速、把模型存下来复用、用 train/val/test 三套数据严谨评估。**这就是 P1 通关验收里"独立搭 PyTorch 训练 pipeline"的样子。**

> 🔗 **本周 bad case 回看锚点（1h）**：PaddleOCR 之所以在你"域外数据"上翻车，往往是因为它训在通用数据上、没在你这份数据上微调/正则化。本周你学的 dropout/weight_decay/评估拆分，正是"让模型适配我的数据、不过拟合训练集"的工具——回想你的 bad case，思考"如果在我这些数据上重训+加正则，会不会更稳"。

## 本周目标

一句话：**给第 5 周的 MLP 加正则化、GPU、模型保存与严谨评估，达成 FashionMNIST 测试集 >90% 的里程碑。**

硬指标：
1. 在模型里加 `nn.Dropout`，理解它为什么能缓解过拟合（训练随机丢弃、测试关闭）
2. 在优化器里加 `weight_decay`（=L2 正则，你第 4 周在损失里见过）
3. 用 `train/val/test` 三套数据，分别用于训练 / 选超参 / 最终报告
4. 模型和数据 `.to(device)` 支持 GPU（无 GPU 退化为 CPU，不影响达标）
5. 用 `state_dict` 保存"最佳模型"并能载入复用
6. **FashionMNIST 测试集准确率 >90%** + 能解释 train/val 曲线（= P1-B 里程碑）

---

## 逐日安排

| 天 | 时长 | 任务 |
|---|---|---|
| Day 1（周一晚） | 1.5h | 读 d2l 第 4 章 权重衰减/dropout（概念）；理解过拟合 |
| Day 2（周二晚） | 1.5h | 写 `ex_classifier.py`：MLP 加 dropout + 优化器加 weight_decay |
| Day 3（周三晚） | 1.5h | 写 train/val 三件套 + GPU `.to(device)` |
| Day 4（周四晚） | 1.5h | 模型保存/加载（state_dict），跑通小数据 |
| Day 5（周五晚） | 1h | 上全量训练，观察 val 曲线，调超参 |
| 周末（选一天） | 4-6h | 冲里程碑 >90% + 画曲线 + 解释 + bad case 回看 1h |

---

## 学什么 & 怎么学

### 模块 A · 过拟合与正则化（Day 1）

**概念清单**：
- **过拟合**：train 很好、val/test 很差 = 死记训练样本，不会泛化（第 3 周已提过）。
- **Dropout**：训练时随机"丢弃"一部分神经元（输出置 0），强迫网络不依赖特定路径 → 等效于训了一堆子网络取平均，抗过拟合。
- **权重衰减（weight_decay）**：在损失里加 `λ·‖W‖²`，惩罚大权重，让决策边界更平滑。它**就是你第 4 周见过的 L2 正则**，只是框架帮你加在优化器里。

**怎么学**：读 d2l 4.5（权重衰减）+ 4.6（dropout）：https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html 。**要能回答："dropout 为什么只在训练时开、测试时关？"**

**产出**：口述两个正则手段的原理，能区分"训练/测试阶段行为差异"。

---

### 模块 B · 给网络加 Dropout + 权重衰减（Day 2）⭐核心动手

**动手**：写 `ex_classifier.py` 的 `MLP`：
- `TODO 1`：在隐藏层后加 `self.drop = nn.Dropout(0.2)`（注意：放在激活之后更常见）。
- `TODO 2`：`forward` 里 `x = self.drop(x)`。
- `TODO 3`：优化器改成 `torch.optim.SGD(..., weight_decay=1e-4)`。

> **关键直觉**：dropout 让"同一结构在训练时每次都略不同"，等价于模型集成，泛化更好；weight_decay 抑制极端权重。两者都是"不让模型太自信地记住训练集"。

**产出**：模型含 dropout + 权重衰减，能前向出 `(B,10)`。

---

### 模块 C · 评估拆分 + GPU（Day 3）

**核心**：严谨评估需要三套数据，各司其职：

| 数据集 | 用途 | 是否在梯度里 |
|---|---|---|
| train | 更新参数 | 是 |
| val | 选超参（lr/dropout 多少）、早停、挑最佳模型 | 否 |
| test | **只在最后报一次**真实泛化能力 | 否 |

> ⚠️ **铁律**：test 集只能最后看一次。平时调参看 val，不然等于"用测试集作弊"。

**动手**：
- `TODO 4`：写 `train_one_epoch`（和第 5 周几乎一样，记得 `model.train()`）。
- `TODO 5`：写 `evaluate`，用 `@torch.no_grad()` + `model.eval()`（关 dropout/BatchNorm 统计）。
- GPU：把 `model` 和每个 `xb,yb` 都 `.to(device)`，`device='cuda' if torch.cuda.is_available() else 'cpu'`。

**产出**：三件套跑通，val 准确率能算。

---

### 模块 D · 模型保存与加载（Day 4）

**核心**：`state_dict` 存的是"参数值"不是"结构"，所以载入时要先有同结构模型。

```python
torch.save(model.state_dict(), 'output/best_model.pt')   # 存
model.load_state_dict(torch.load('output/best_model.pt')) # 载入（需先实例化同结构 model）
```

**动手**：`TODO 6/7`：训练时若 val_acc 创新高就 `save_model(model)`；训练结束后 `load_model` 再在 test 上报一次。**只报一次 test，这是诚实的泛化指标。**

**产出**：最佳模型落盘且能载入复用；test 准确率可信。

---

### 周末 · 冲里程碑 + 解释曲线 + 回看（4-6h）

**1. 冲 >90%**：通常 `隐藏层128/256 + dropout 0.2 + weight_decay 1e-4 + 10 epoch` 能上 90%。调不动就：
- 隐藏层加大到 256
- 学习率试 0.05 / 0.2
- epoch 加到 15-20

**2. 画 + 解释曲线**：`output/week6_curve.png`。**解释要点**（写进 `notes.md`）：
- train loss 持续降、val loss 先降后平/回升 = 过拟合信号 → 加 dropout/weight_decay
- 若 train/val 都高 = 欠拟合 → 模型/训练还不够
- 准确率 plateau 后还上不去，看是不是学习率太小

**3. 消融对照（强烈建议）**：把 dropout/weight_decay 去掉重跑一次，看 val 曲线是不是更早变差——**亲手看到正则化的效果，比看书十遍管用**。

**4. bad case 回看（1h）**：结合"正则/适配域数据"，写一句："我的 bad case 若在我这份数据上重训+加正则，泛化会更稳。" 记进日志。

**产出（= P1-B 里程碑）**：FashionMNIST >90% + 可解释的 train/val 曲线 + 最佳模型文件。

---

## 本周资源清单

| 用途 | 链接 |
|---|---|
| d2l 第 4 章 权重衰减 / dropout | https://zh.d2l.ai/chapter_multilayer-perceptrons/index.html |
| PyTorch 保存/加载模型官方文档 | https://pytorch.org/tutorials/beginner/saving_loading_models.html |
| PyTorch 优化器（weight_decay 参数） | https://pytorch.org/docs/stable/optim.html |
| 李沐视频（对应 d2l，B 站「跟李沐学AI」） | B 站搜「跟李沐学AI」 |

---

## 验收清单（周末打勾）

- [ ] 模型加了 `nn.Dropout`，且能解释"为何训练开、测试关"
- [ ] 优化器加了 `weight_decay`（L2 正则），能说清它等于第 4 周的什么
- [ ] 用了 train/val/test 三套数据，test 只在最后报一次
- [ ] 模型 + 数据 `.to(device)`，支持 GPU（无 GPU 退 CPU 也达标）
- [ ] 用 `state_dict` 保存最佳模型并可载入复用
- [ ] **FashionMNIST 测试集准确率 >90%**（P1-B 里程碑）
- [ ] 画出 train/val 曲线并能解释（含过拟合判断）
- [ ] 完成一次 bad case 回看并记录（聚焦"正则/适配域数据"）

---

## 常见坑 & 卡住怎么办

- **测试准确率比验证低很多**：你可能用 test 调过参（作弊）。记住 test 只看最后 1 次；平时调参用 val。
- **加了 dropout 后 train acc 掉到很低**：正常！dropout 训练时削弱网络，test 关掉后恢复。看 test/val 才有意义，别被 train acc 吓到。
- **GPU 跑报错 "expected device cuda but got cpu"**：数据和模型必须**都** `.to(device)`。最常见漏的是 `xb, yb = xb.to(device), yb.to(device)`。
- **没 GPU 很慢**：降到 `batch_size=64`、隐藏层 128、10 epoch 也能到 90% 左右；或用 Colab/AutoDL 白嫖 GPU。
- **保存后载入报错 size mismatch**：载入时的 model 必须和保存时**结构完全一致**（同隐藏层大小等）。
- **卡在 88% 上不去**：① 隐藏层加到 256；② epoch 加到 20；③ lr 试 0.2；④ 确认数据真的 `÷255` 了。
- **卡住 >2h**：回 d2l 第 4 章 + PyTorch 官方 saving/loading 文档，别死磕。

---

## 进度日志（本周日填）

```
第 6 周（日期 ____）｜阶段 P1-B（下 · 里程碑）
· 本周跑通了什么：____________________（完整 pipeline + 模型保存）
· 测试集准确率：____%（里程碑目标 >90%）
· 加了哪些正则：dropout=____ / weight_decay=____
· 去掉正则后 val 曲线变化：____________（消融对照）
· 曲线我看出了什么（过拟合/欠拟合信号）：____________
· bad case 回看的新理解：____________
· 卡在哪、怎么解决的：________________
· ✅ P1-B 是否通关（能独立搭 PyTorch pipeline 吗）：____________
· 下周（P1-C CNN 原理）第一件事：____________
```
