# 缺失值处理的三种策略

> 来源：Kaggle《Intermediate Machine Learning》课程精华
> 覆盖：Missing Values

---

## 一、先诊断：哪些列缺、缺多少

```python
# 每列缺失值个数
cols_with_missing = [col for col in X_train.columns if X_train[col].isnull().any()]

# 更完整的信息
X_train.isnull().sum()
```

**处理前必须先看缺失比例和缺失原因**——缺失本身可能就是信息（比如"没填车库年份"可能意味着"没有车库"）。

---

## 二、三种策略

### 策略 1：直接删列（Drop）

```python
cols_with_missing = [col for col in X_train.columns
                     if X_train[col].isnull().any()]
reduced_X_train = X_train.drop(cols_with_missing, axis=1)
reduced_X_test = X_test.drop(cols_with_missing, axis=1)
```

- **优点**：简单粗暴，绝不引入假数据
- **缺点**：整列信息全部扔掉。列里 95% 的值是好的、只有 5% 缺失？也全扔
- **适用**：缺失比例极高（如 >50%）且该列不重要的场景

### 策略 2：填充（Imputation）

```python
from sklearn.impute import SimpleImputer

imputer = SimpleImputer()                     # 默认策略：均值填充
imputed_X_train = pd.DataFrame(imputer.fit_transform(X_train))
imputed_X_test = pd.DataFrame(imputer.transform(X_test))

# fit_transform 会丢掉列名，手动加回来
imputed_X_train.columns = X_train.columns
imputed_X_test.columns = X_test.columns
```

- 数值列默认填**均值**（也可 `strategy='median'` 填中位数，抗极端值更好）
- **优点**：保住整列数据，模型往往比删列表现更好
- **缺点**：填进去的是"编造"的值，可能引入偏差
- **适用**：大多数情况的默认选择

⚠️ **fit/transform 分离**：`imputer.fit` 只能在训练集上算均值，然后同一个 imputer `transform` 训练集和测试集——否则测试集信息泄漏进训练过程（和 target encoding 的泄漏是同一类错误）。

### 策略 3：填充 + 缺失指示列（Imputation + Indicator）

```python
X_train_plus = X_train.copy()
X_test_plus = X_test.copy()

for col in cols_with_missing:
    X_train_plus[col + '_was_missing'] = X_train[col].isnull()
    X_test_plus[col + '_was_missing'] = X_test[col].isnull()

# 然后再做填充
imputed_X_train_plus = pd.DataFrame(imputer.fit_transform(X_train_plus))
```

- 在填充的基础上，额外加一列布尔值标记"这个值原本是不是缺的"
- **为什么有用**："缺失"本身可能携带预测信息（没填车库年份 → 可能没车库 → 影响房价）。均值填充抹掉了这个信号，指示列把它找回来
- **适用**：怀疑缺失不是随机的时候，值得尝试

---

## 三、策略对比与选择

| 策略 | 信息保留 | 风险 | 何时用 |
|---|---|---|---|
| 删列 | 丢失整列 | 无假数据 | 缺失极多、列不重要 |
| 填充 | 保留大部分 | 引入编造值 | **默认首选** |
| 填充+指示列 | 保留最多 | 略增复杂度 | 缺失可能有含义时 |

**没有绝对最优——跑一遍 MAE 对比，让验证分数说话。** 课程实验结论：在多数数据集上，填充（尤其带指示列）≥ 删列。

---

## 四、一句话总结

**缺失值三板斧：删（简单但丢信息）、填（默认选择）、填+标记（把"缺失本身"当特征用）；用验证集 MAE 实测对比，别拍脑袋。**
