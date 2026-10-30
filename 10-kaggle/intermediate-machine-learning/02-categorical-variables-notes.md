# 分类变量处理的三种策略

> 来源：Kaggle《Intermediate Machine Learning》课程精华
> 覆盖：Categorical Variables

---

## 一、什么是分类变量

取值是**离散类别**而非连续数值的列，如 `Condition`（好/中/差）、`Color`（红/绿/蓝）。sklearn 的大多数模型只吃数字，必须先编码。

**基数（Cardinality）** = 该列不同取值的个数。基数大小直接决定用哪种策略。

---

## 二、三种策略

### 策略 1：删列（Drop）

```python
object_cols = [col for col in X_train.columns if X_train[col].dtype == "object"]
low_cardinality_cols = [col for col in object_cols if X_train[col].nunique() < 10]
drop_cols = [col for col in object_cols if col not in low_cardinality_cols]

X_train.drop(drop_cols, axis=1, inplace=True)
```

- 基数太高的列（如 ZIP code、身份证号），one-hot 会炸出几千列，删掉最省事
- **代价**：信息全丢

### 策略 2：标签编码（Label Encoding）

每个类别分配一个整数：`红→0, 绿→1, 蓝→2`

```python
from sklearn.preprocessing import LabelEncoder

label_X_train = X_train.copy()
for col in object_cols:
    label_X_train[col] = LabelEncoder().fit_transform(X_train[col])
```

- **优点**：不增加列数，高基数也不怕
- **致命缺点**：**整数引入了不存在的大小关系**。模型会以为 `蓝(2) > 绿(1) > 红(0)`，但颜色没有顺序！
- **适用**：类别**本身有序**时（如学历：小学<中学<大学；评级：差<中<好）。类别无序时用它会误导模型
- ⚠️ 遇到训练时没见过的类别会报错，需要额外处理

### 策略 3：独热编码（One-Hot Encoding）

每个类别变成一列 0/1：

```
原始 Color 列          →  Color_红  Color_绿  Color_蓝
红                       1         0         0
绿                       0         1         0
蓝                       0         0         1
```

```python
from sklearn.preprocessing import OneHotEncoder

OH_encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False)
OH_cols_train = pd.DataFrame(OH_encoder.fit_transform(X_train[object_cols]))
OH_cols_train.columns = OH_encoder.get_feature_names_out(object_cols)
```

- **优点**：不引入虚假的大小关系，最"诚实"的编码
- **缺点**：列数爆炸——基数 10000 的列变 10000 列
- `handle_unknown='ignore'`：**测试集出现训练时没见过的类别 → 全 0 行**，不报错（生产必备）
- **适用**：基数低（<10 左右）、类别无序的列

---

## 三、决策表

| 情况 | 推荐策略 |
|---|---|
| 类别本身有序（评级、学历） | 标签编码（或有序映射） |
| 无序 + 低基数 | **独热编码** |
| 无序 + 高基数（几千个取值） | 删列，或 target encoding（见 feature-engineering/07 笔记） |
| 拿不准 | 低基数列 one-hot，高基数列删，跑验证分数对比 |

### 与 Target Encoding 的衔接

feature-engineering 课程里学过：**能用 one-hot 优先 one-hot（保留完整信息、无泄漏风险）；类别数太多、one-hot 撑不住时，才上 target encoding**（用目标均值编码，配合平滑和交叉验证防泄漏）。两门课的策略在这里汇合了。

---

## 四、一句话总结

**分类变量三板斧：删（高基数弃车保帅）、标签编码（仅用于天然有序的类别）、独热（无序低基数的默认选择）；判断依据是基数大小和类别有无天然顺序。**
