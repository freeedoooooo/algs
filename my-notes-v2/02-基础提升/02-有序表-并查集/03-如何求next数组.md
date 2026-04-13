# 如何求next数组？

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：待补充
- 所属分类：基础提升
- 所属章节：02 有序表、并查集
- 原始条目：☐ 如何求next数组？

## 笔记
下面示例中第一个?是脚标是i-1，N的脚标是i；

cn有2个含义，示例中cn开始等于8：

什么位置的元素与?对比；

?的next值为8，如果e=?，则index[i-1]=8+1=9

// cn+1

// next赋值

// 指针右移

next[i++]=++cn

0123456789

abbstabbecabbstabb?N

e=?，next[N]=9，否则从e跳到s

abbstabbecabbstabb?N

s=?，next[N]=4，否则从s跳到a

abbstabbecabbstabb?N

a=?，next[N]=1，否则next[i]=0
