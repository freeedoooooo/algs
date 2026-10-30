# 模型验证：MAE、欠拟合与过拟合

> 来源：Kaggle《Intro to Machine Learning》课程精华
> 覆盖：Model Validation / Underfitting and Overfitting

---

## 一、模型验证：MAE

### 1.1 为什么需要验证集

用训练数据评估自己 = 用做过的原题考试。必须**留出一部分模型没见过的数据**来打分。

```python
from sklearn.model_selection import train_test_split

train_X, val_X, train_y, val_y = train_test_split(X, y, random_state=0)

model = DecisionTreeRegressor(random_state=1)
model.fit(train_X, train_y)          # 只用训练集学
val_predictions = model.predict(val_X)
```

### 1.2 MAE：平均绝对误差

$$MAE = \frac{1}{n}\sum_{i=1}^{n}|预测值_i - 真实值_i|$$

```python
from sklearn.metrics import mean_absolute_error

print(mean_absolute_error(val_y, val_predictions))
# 输出比如 29652 —— 平均每套房价预测偏差 2.9 万
```

- **绝对值**：预测偏高偏低同等对待，正负不会互相抵消
- **单位和目标一致**：房价的 MAE 单位是"元"，直观可解释
- **越小越好**

*类比：射击打靶，MAE = 每发子弹离靶心距离的平均值。*

### 1.3 回归常用指标对比

| 指标 | 公式特点 | 优点 | 缺点 |
|---|---|---|---|
| **MAE** | 绝对误差平均 | 直观、抗极端值 | 处处斜率相同，优化时信号不变 |
| **MSE / RMSE** | 平方误差 | 放大大误差、可导性好 | 受极端值影响大 |
| **MAPE** | 百分比误差 | 跨量纲可比 | 真实值接近 0 时爆炸 |

入门阶段记住 MAE 即可。

---

## 二、欠拟合与过拟合

### 2.1 核心矛盾：模型复杂度

```
验证集 MAE
  ↑
  |  \                   /
  |   \                 /      ← 过拟合区：树太深，
  |    \               /         连噪声都背下来了
  |     \___       ___/
  |         \_____/  ← 最佳点（甜区）
  |    ↑
  |  欠拟合区：树太浅，规律都没学到
  +——————————————————————→ 模型复杂度（如叶子数）
```

| 状态 | 表现 | 原因 | 类比 |
|---|---|---|---|
| **欠拟合** Underfitting | 训练差、验证也差 | 模型太简单，捕捉不到规律 | 用直线拟合曲线 |
| **过拟合** Overfitting | 训练好、验证差 | 模型太复杂，把训练数据的噪声当规律背下来 | 死记硬背原题，换个说法就不会 |
| **刚好** | 验证 MAE 最低 | 复杂度适中 | 学会了规律，没背噪声 |

**判断方法：比较训练集和验证集的表现差距。** 差距大 = 过拟合；两个都差 = 欠拟合。

### 2.2 实践：调 max_leaf_nodes 找甜区

```python
def get_mae(max_leaf_nodes, train_X, val_X, train_y, val_y):
    model = DecisionTreeRegressor(max_leaf_nodes=max_leaf_nodes, random_state=0)
    model.fit(train_X, train_y)
    preds = model.predict(val_X)
    return mean_absolute_error(val_y, preds)

# 网格扫描不同的叶子数，选 MAE 最小的
for max_leaf_nodes in [5, 50, 500, 5000]:
    print(get_mae(max_leaf_nodes, train_X, val_X, train_y, val_y))
```

控制决策树复杂度的常用参数：

| 参数 | 作用 | 调小 → |
|---|---|---|
| `max_leaf_nodes` | 最多叶子数 | 更简单，抗过拟合 |
| `max_depth` | 树的最大深度 | 同上 |
| `min_samples_leaf` | 每个叶子最少样本数 | 叶子更"平均"，抗过拟合 |

### 2.3 为什么过拟合能发生？

数据 = 真实规律 + 随机噪声。模型足够复杂时，有能力把噪声也"解释"进去——训练集上完美，但这些噪声在新数据上不会重现，于是预测崩掉。

**样本越少、模型越复杂，过拟合风险越大。**

---

## 三、一句话总结

**验证集 + MAE 是模型的"考试"；欠拟合是学得太少，过拟合是背得太多；用 max_leaf_nodes 等参数扫描复杂度，找验证 MAE 最低的甜区。**
