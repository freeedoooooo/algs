"""
第5周脚手架 · 环境验证（直接运行）

确认 PyTorch 装好、能否用 GPU、做一个最小的张量运算自检。
敲这个学不到深度学习，所以替你写好——跑通即可，省下精力给 ex_*.py。
"""
import torch


def main():
    print('PyTorch 版本:', torch.__version__)
    cuda_ok = torch.cuda.is_available()
    print('CUDA 可用:', cuda_ok)
    if cuda_ok:
        print('GPU 名称:', torch.cuda.get_device_name(0))
    else:
        print('（无 GPU，本周全部用 CPU 即可，不影响学习；GPU 加速第6周再说）')

    # 最小张量运算自检：应该能算 (3,4) @ (4,2) = (3,2)
    a = torch.randn(3, 4)
    b = torch.randn(4, 2)
    c = a @ b
    assert c.shape == (3, 2), f'矩阵乘法结果形状异常: {c.shape}'
    print('张量 matmul 自检通过，shape =', tuple(c.shape))

    # 设备一致性自检
    device = 'cuda' if cuda_ok else 'cpu'
    x = torch.randn(2, 2).to(device)
    print(f'张量已放到 {device}，值示例:\n', x)


if __name__ == '__main__':
    main()
