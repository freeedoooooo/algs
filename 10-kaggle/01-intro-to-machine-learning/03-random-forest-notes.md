# 随机森林与竞赛工作流

> 来源：Kaggle《Intro to Machine Learning》课程精华
> 覆盖：Random Forests / Machine Learning Competitions

---

## 一、随机森林：三个臭皮匠顶个诸葛亮

### 1.1 单棵决策树的问题

上一课用 `max_leaf_nodes` 调复杂度找甜区，但始终两难：
- 树深 → 过拟合
- 树浅 → 欠拟合

**随机森林换了思路：不再纠结单棵树的复杂度，而是种很多棵深树，取平均。**

### 1.2 原理：Bagging（装袋法）

```python
from sklearn.ensemble import RandomForestRegressor

forest_model = RandomForestRegressor(random_state=1)
forest_model.fit(train_X, train_y)
preds = forest_model.predict(val_X)
```

内部做了两件事：

1. **数据随机**：每棵树只用**有放回抽样**出来的一份训练数据（约 63% 的原始样本，叫 bootstrap 样本）
2. **特征随机**：每次分裂时只考虑**随机一部分特征**（默认约 √特征数），而不是全部

然后对几百棵树的预测**取平均**作为最终结果。

### 1.3 为什么取平均有效？

每棵树都过拟合了，但**各自过拟合的方向不同**（因为看到的数据和特征都是随机的）。误差互相抵消：

*类比：让 500 个水平一般的人估计一头牛的重量，单个人的误差五花八门，但 500 人答案的平均值往往惊人地准——这就是"群体智慧"。*

数学上：平均 N 个独立预测，方差降为原来的约 1/N。**单棵树的高方差被"民主投票"抹平了。**

### 1.4 决策树 vs 随机森林

| | 决策树 | 随机森林 |
|---|---|---|
| 复杂度控制 | 需要手动调 max_leaf_nodes | 默认就深树+平均，几乎不用调 |
| 过拟合风险 | 高 | 低（单树过拟合被平均抵消） |
| 训练速度 | 快 | 慢（几百棵树） |
| 可解释性 | 强（能画出来看） | 弱（但能给特征重要性） |
| 默认效果 | 一般 | 好，**表格数据基线首选** |

**实践习惯：拿到新数据集，先跑一个默认参数的随机森林作为基线，再考虑优化。**

---

## 二、竞赛工作流：从训练到提交

### 2.1 竞赛数据和平时练习的区别

| 数据文件 | 有无目标列 y | 用途 |
|---|---|---|
| `train.csv` | 有 | 训练 + 本地验证 |
| `test.csv` | **没有** | 只能预测，提交给平台打分 |

**关键约束：测试集没有答案，无法本地算 MAE。** 所以本地验证必须靠从 train 中切分出的 val 集。

### 2.2 标准提交流程

```python
# 1. 读数据
train_data = pd.read_csv('train.csv')
test_data = pd.read_csv('test.csv')

# 2. 划分特征和目标
y = train_data.SalePrice
features = ["LotArea", "YearBuilt", "1stFlrSF", "2ndFlrSF", "FullBath", "BedroomAbvGr", "TotRmsAbvGrd"]
X = train_data[features]

# 3. 本地验证（train/val 切分），确认效果
train_X, val_X, train_y, val_y = train_test_split(X, y, random_state=1)
# ... fit + predict + mean_absolute_error ...

# 4. 效果满意后，用【全部训练数据】重新训练最终模型
final_model = RandomForestRegressor(random_state=1)
final_model.fit(X, y)              # 注意：这次不切分，用满所有数据

# 5. 预测测试集
test_preds = final_model.predict(test_data[features])

# 6. 生成提交文件（格式必须是 Id + 预测列）
output = pd.DataFrame({'Id': test_data.Id, 'SalePrice': test_preds})
output.to_csv('submission.csv', index=False)
```

### 2.3 两个容易踩的坑

1. **特征列表必须一致**：训练用的 features 和预测 test 时用的必须完全相同，顺序也要相同
2. **提交格式必须严格匹配**：`index=False` 别漏（多一列 index 会判格式错误）；列名要和竞赛要求一致
3. **最终模型用全量训练数据**：验证阶段用 train/val 切分选参数，选定后重新 fit 全部数据——多 25% 的数据通常能让测试分数更好

*Java 类比：submission.csv 就是接口的响应 DTO，字段名、类型必须和契约（竞赛要求）完全一致，差一点就 400。*

---

## 三、一句话总结

**随机森林 = 很多棵各自随机过拟合的深树取平均，方差互相抵消，是表格数据的默认基线；竞赛流程 = 本地用 train 切 val 验证 → 全量数据重训最终模型 → 预测 test 生成 submission.csv。**
