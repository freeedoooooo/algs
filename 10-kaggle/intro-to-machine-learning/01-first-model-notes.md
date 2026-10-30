# 第一个机器学习模型：决策树

> 来源：Kaggle《Intro to Machine Learning》课程精华
> 覆盖：How Models Work / Basic Data Exploration / Your First Machine Learning Model

---

## 一、模型是怎么"学习"的

### 1.1 决策树的直觉

以预测房价为例，决策树就是一连串 if-else：

```
这套房子的房间数 > 5 吗？
├── 是 → 面积 > 2000 平米吗？
│       ├── 是 → 预测 35 万
│       └── 否 → 预测 28 万
└── 否 → 预测 18 万
```

- **叶子节点** = 最终的预测值（通常是该叶子内所有训练样本的平均值）
- **分裂条件** = 模型从数据中自动学出来的，不是人写的

*Java 类比：`fit` 就像 Spring 容器初始化时注入配置，`predict` 就是调用一个已经构建好的纯函数。训练阶段（fit）产生状态，推理阶段（predict）只读状态。*

### 1.2 机器学习的本质

**从历史数据中自动找出"特征 → 目标"的映射规则**，然后用这个规则对新数据做预测。人不需要手写规则（对比传统编程：if-else 是人写的，ML 的规则是数据"喂"出来的）。

---

## 二、基础数据探索（Pandas 核心操作）

```python
import pandas as pd

home_data = pd.read_csv('melb_data.csv')

home_data.describe()      # 每个数值列的统计摘要
```

`describe()` 输出中最重要的几个指标：

| 指标 | 含义 | 用途 |
|---|---|---|
| **count** | 非缺失值个数 | 判断有没有缺失 |
| **mean / std** | 均值 / 标准差 | 了解数据分布中心和离散程度 |
| **min / max** | 极值 | 发现异常值（如 max 是 mean 的 100 倍） |
| **25% / 50% / 75%** | 分位数 | 50% 就是中位数，不受极端值影响 |

**先 describe 再建模**是铁律：不先看数据分布就直接训练，等于闭着眼睛开车。

---

## 三、第一个模型：三步走

### 3.1 完整代码

```python
from sklearn.tree import DecisionTreeRegressor

# 1. 定义特征和目标
y = home_data.Price                        # 目标变量（预测什么）
features = ["Rooms", "Bathroom", "Landsize", "Lattitude", "Longtitude"]
X = home_data[features]                    # 特征矩阵（用什么预测）

# 2. 定义并训练模型
model = DecisionTreeRegressor(random_state=1)   # 固定随机种子，结果可复现
model.fit(X, y)                           # 学习：从 X、y 中找出规则

# 3. 预测
print(model.predict(X.head()))            # 对前 5 行做预测
```

### 3.2 每一行在干什么

| 代码 | 作用 | 关键点 |
|---|---|---|
| `y = home_data.Price` | 取出要预测的目标列 | y 是一维 Series |
| `X = home_data[features]` | 取出用于预测的特征列 | X 是二维 DataFrame，**大写 X 表示矩阵** |
| `DecisionTreeRegressor(random_state=1)` | 创建回归树模型 | Regressor=预测连续值；Classifier=预测类别 |
| `model.fit(X, y)` | **训练**：自动学出树的分裂结构 | 这是唯一"学习"发生的地方 |
| `model.predict(...)` | **推理**：用学好的树对新数据打分 | 不会改变模型状态 |

### 3.3 约定俗成的命名

- **X（大写）** = 特征矩阵（多列）
- **y（小写）** = 目标变量（一列）

这是整个 ML 社区的通用约定，看任何教程都是这个写法。

### 3.4 Regressor vs Classifier

| 类型 | 预测的东西 | 例子 | sklearn 类名后缀 |
|---|---|---|---|
| 回归 Regressor | 连续数值 | 房价、温度、销量 | `...Regressor` |
| 分类 Classifier | 离散类别 | 垃圾邮件/正常、猫/狗 | `...Classifier` |

---

## 四、一个致命陷阱：用自己训练的数据验证自己

```python
print(model.predict(X.head()))   # 预测值和真实值几乎一样！
```

上面的预测看起来"准得惊人"，因为模型就是从这些数据里学的——**它记住了答案，不是学会了规律**。

就像让学生用做过的原题考试，100 分说明不了任何问题。

下一篇（02-model-validation-notes.md）解决这个问题：**留出验证集**。

---

## 五、一句话总结

**ML 模型 = fit（从数据学规则）+ predict（用规则对新数据打分）；X 是特征矩阵，y 是目标；但绝不能用训练数据本身评估模型好坏。**
