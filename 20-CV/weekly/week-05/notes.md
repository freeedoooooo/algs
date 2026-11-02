# 第 5 周笔记（P1-B 上 · PyTorch 入门）

## 一句话总结本周
-

## Tensor & autograd（对照第4周 numpy 手写）
- `requires_grad` 是什么：
- `backward()` 在算什么（= 第4周我手写的哪一步）：
- `.grad` 存的是什么：

## nn.Module：我搭的 MLP 结构
- 层结构（画一下）：
- 参数量有多少（对比第4周 784×128+128×10）：

## 训练循环：PyTorch 哪一步对应我第4周手写的哪一步
| 第4周 numpy | 第5周 PyTorch |
|---|---|
| 手写 forward | |
| 手写 backward | |
| 手写参数更新 W -= lr*dW | |

## 卡住的点 & 解决
-

## bad case 回看（PaddleOCR 输入预处理）
- 我 P0 跑 PaddleOCR 时图片做了什么预处理？本周 DataLoader 的 ToTensor/255 对应哪一步？
