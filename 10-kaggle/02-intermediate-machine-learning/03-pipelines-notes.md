# Pipeline：把预处理和模型打包成流水线

> 来源：Kaggle《Intermediate Machine Learning》课程精华
> 覆盖：Pipelines

---

## 一、没有 Pipeline 时的痛点

前两课的代码是这样组织的：

```python
# 1. 手动挑出数值列、分类列
# 2. 数值列做 imputer，得到 DataFrame A
# 3. 分类列做 one-hot，得到 DataFrame B
# 4. pd.concat 把 A、B 拼回去
# 5. model.fit(...)
# 6. 测试集再把 2-5 全部重做一遍……
```

问题：
- **代码冗长易错**：训练集、验证集、测试集每一套都要重复整个流程
- **顺序容易搞错**：忘了先 impute 再 fit，或测试集用了不同的处理参数
- **难以交叉验证**：`cross_val_score` 只接受"一步到位"的模型

---

## 二、Pipeline 的写法

### 2.1 完整示例

```python
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor

# 数值列的处理步骤
numerical_transformer = SimpleImputer(strategy='constant')

# 分类列的处理步骤
categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),   # 类别列填众数
    ('onehot', OneHotEncoder(handle_unknown='ignore'))
])

# 把两条处理线组装到各自的列上
preprocessor = ColumnTransformer(
    transformers=[
        ('num', numerical_transformer, numerical_cols),
        ('cat', categorical_transformer, categorical_cols)
    ])

# 预处理 + 模型 = 一条完整流水线
model = RandomForestRegressor(n_estimators=100, random_state=0)
my_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('model', model)
])
```

### 2.2 用起来有多爽

```python
# 训练：一行
my_pipeline.fit(X_train, y_train)

# 预测：一行（预处理自动执行）
preds = my_pipeline.predict(X_test)
```

不需要再手动对测试集做 impute/one-hot——**Pipeline 记住了训练时学到的所有参数（均值、众数、类别映射），predict 时自动套用**。

### 2.3 结构类比

*Java 类比：Pipeline 就是 Servlet Filter 链 / Spring Interceptor 链——数据依次流过每个环节，每个环节只做自己的事，外部只看到一个统一入口（fit/predict）。ColumnTransformer 则是按"路由规则"（列名）把请求分发给不同的处理器。*

```
原始数据 → [num: imputer]        ↘
         → [cat: imputer→onehot]  → 拼接 → [model: RandomForest] → 预测
```

---

## 三、Pipeline 的三大价值

| 价值 | 说明 |
|---|---|
| **代码更干净** | 预处理+模型一个对象，fit/predict 各一行 |
| **杜绝顺序错误** | 处理和模型的执行顺序被结构固化，不可能漏步骤或用错参数 |
| **支持交叉验证** | `cross_val_score(my_pipeline, X, y)` 直接把整条流水线当一个模型验证 |

第三条尤其重要：交叉验证的每一折都需要"用该折训练集重新学预处理参数"，Pipeline 天然保证了这一点，手动代码几乎必错。

---

## 四、一句话总结

**Pipeline = 预处理 + 模型的责任链：ColumnTransformer 按列路由（数值列填充、分类列填充+one-hot），组装成一个对象后 fit/predict 一行搞定，且天然兼容交叉验证、杜绝训练测试处理不一致。**
