# 交叉验证：让模型评估更可靠

> 来源：Kaggle《Intermediate Machine Learning》课程精华
> 覆盖：Cross-Validation

---

## 一、单次 train/val 切分的问题

```python
train_X, val_X, train_y, val_y = train_test_split(X, y, test_size=0.2)
```

问题：**分数取决于切到哪一批数据当验证集**。

- 运气好切到一批"简单"样本 → MAE 虚低 → 误以为模型很好
- 运气差切到一批"难"样本 → MAE 虚高 → 误杀好模型
- 数据量小的时候尤其严重：val 集只有几十条，随机波动巨大

*类比：面试官只问一个问题就决定录用——问题恰好是候选人复习过的，评估就失真了。*

---

## 二、K 折交叉验证（K-Fold Cross-Validation）

### 2.1 原理

把数据分成 K 份（常用 5 份），轮流让每一份当验证集：

```
第 1 轮：[val][train][train][train][train]
第 2 轮：[train][val][train][train][train]
第 3 轮：[train][train][val][train][train]
第 4 轮：[train][train][train][val][train]
第 5 轮：[train][train][train][train][val]

最终分数 = 5 轮分数的平均值
```

每个样本都当过一次验证数据，**分数是"5 次考试的平均分"**，比单次切分稳定得多。

### 2.2 代码

```python
from sklearn.model_selection import cross_val_score

# 注意：sklearn 的 score 约定"越大越好"，所以 MAE 取负数
scores = -1 * cross_val_score(my_pipeline, X, y,
                              cv=5,                          # 5 折
                              scoring='neg_mean_absolute_error')

print("Average MAE:", scores.mean())
print("MAE std:", scores.std())      # 各折分数的波动，越小越可靠
```

**两个细节：**
- `scoring='neg_mean_absolute_error'`：误差类指标越小越好，sklearn 统一取负转成"越大越好"，所以乘 -1 还原
- 和 Pipeline 配合使用：每一折内部，预处理参数都只用该折训练数据重新学习，**不会泄漏**

---

## 三、什么时候用交叉验证

| 场景 | 建议 |
|---|---|
| **小数据集**（< 几万行） | 用 CV。单次切分波动太大 |
| **大数据集**（几十万行以上） | 单次 train/val 切分就够——数据多了，随机波动自然小，且 CV 要训练 5 个模型，很慢 |
| 模型选择、调参、论文/比赛报告 | 用 CV，结论更可信 |

课程的参考阈值：**数据量在 10 万行以内基本都建议用 CV**（Kaggle 笔记本算力下 5 折可接受）。

### 代价

训练时间 × K。5 折 = 训练 5 个模型。这是"评估可靠性"和"计算成本"的交换。

---

## 四、一句话总结

**交叉验证 = 轮流用每一份数据当验证集，取平均分，消除"切分运气"对评估的影响；小数据集必用（cv=5），大数据集单次切分即可；sklearn 中误差指标以负数形式传入 scoring 参数。**
