# XGBoost：梯度提升树

> 来源：Kaggle《Intermediate Machine Learning》课程精华
> 覆盖：XGBoost

---

## 一、从随机森林到梯度提升

同样是"很多棵树的集成"，思路相反：

| | 随机森林（Bagging） | 梯度提升（Boosting） |
|---|---|---|
| 树怎么长 | 各自独立、并行生长 | **串行**：每棵树专门纠正前面所有树的残余错误 |
| 单棵树 | 深树（容易过拟合，靠平均抵消） | **浅树**（弱学习器，单棵很弱） |
| 合成方式 | 取平均 | 加权累加 |
| 类比 | 500 人独立投票 | 一个学生反复刷错题本 |

*Java 类比：随机森林像多线程并行执行再汇总结果；梯度提升像循环里每次迭代都在上一次结果的基础上做增量修正。*

---

## 二、原理：错题本学习法

```
初始预测 = 均值
第 1 棵树：学习"真实值 - 当前预测"的残差（错题）
更新预测 = 原预测 + 学习率 × 第1棵树的输出
第 2 棵树：学习更新后的新残差（还没改对的错题）
更新预测 = ...
第 N 棵树：...

最终预测 = 初始值 + 学习率 × (树1 + 树2 + ... + 树N) 的输出累加
```

每棵树只需要比瞎猜好一点点（弱学习器），几百棵叠加后就很强。这就是 Boosting 的核心：**化弱为强**。

### 为什么叫"梯度"提升

每棵树拟合的"残差"，数学上就是损失函数的**负梯度**方向——沿着梯度反方向一小步一小步下山。和神经网络的梯度下降是同一套优化思想，只是"参数"换成了"树"。

---

## 三、XGBoost 实战

### 3.1 基础用法

```python
from xgboost import XGBRegressor

model = XGBRegressor(random_state=0)
model.fit(X_train, y_train)
preds = model.predict(X_val)
```

### 3.2 三个关键参数

#### ① n_estimators：迭代几轮（几棵树）

```python
model = XGBRegressor(n_estimators=1000, random_state=0)
```

- 太小 → 欠拟合；太大 → 过拟合（错题本背下来了）
- **配合 early stopping 用，不用手调**

#### ② early_stopping_rounds：自动找最佳轮数

```python
model = XGBRegressor(n_estimators=1000, random_state=0)
model.fit(X_train, y_train,
          early_stopping_rounds=5,
          eval_set=[(X_val, y_val)],
          verbose=False)
```

逻辑：把 n_estimators 设大（如 1000），每加一棵树就看验证分数——**连续 5 轮没提升就停**，自动保留最好那一刻的模型。

*类比：爬山时连续 5 步都没升高，就停在历史最高点，不再瞎走。*

#### ③ learning_rate：每棵树的贡献打几折

```python
model = XGBRegressor(n_estimators=3000, learning_rate=0.05, random_state=0)
```

- 默认 0.1：每棵树的修正只采纳一部分，避免单棵树影响过大
- **调小学习率 + 加大树数 = 更精细的修正，通常效果更好**（0.05 + 3000 树是常见组合）
- 代价：训练更慢

### 3.3 调参口诀

1. `n_estimators=500~3000` + `early_stopping_rounds=5` → 让早停自动定树数
2. 有余力再把 `learning_rate` 从 0.1 降到 0.05，同时把 n_estimators 翻倍
3. 其余参数（max_depth、subsample 等）入门阶段不动，默认值已经不错

---

## 四、XGBoost 在表格数据界的地位

- Kaggle 表格类竞赛的**统治级模型**，长年霸榜
- 内置处理：正则化项（抗过拟合）、缺失值自动学习分裂方向、并行特征扫描
- 比随机森林通常高 1~3 个点的精度，且支持增量调优

---

## 五、一句话总结

**XGBoost = 串行生长的浅树集成，每棵树纠正前面所有树的残差（错题本学习法）；实战三板斧：大 n_estimators + early_stopping_rounds=5 + 小 learning_rate，让早停自动找最佳轮数。**
