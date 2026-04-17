# Map中的key区分引用传递，还是值传递（基础类型、String都是值传递）

[返回章节](README.md) | [返回分类](../README.md) | [返回总目录](../../README.md)

- 状态：已标记完成
- 所属分类：基础巩固
- 所属章节：02 链表、栈、队列、递归行为、哈希表、有序表
- 原始条目：☒ Map中的key区分引用传递，还是值传递（基础类型、String都是值传递）

## 一句话结论
在 Java 里，方法参数传递本质上只有一种：值传递。
区别只在于这个“值”是什么。基础类型传的是数值本身；引用类型传的是“引用地址的副本”，而 `Map` 判断 key 是否相同，最终看的是 `equals()` 和 `hashCode()`，不是“引用传递”四个字。

## 核心知识点
- Java 没有“引用传递”，只有值传递。
- 基础类型传的是实际值，如 `int`、`double`。
- 引用类型传的是“引用变量里保存的地址值”。
- `String` 虽然是引用类型，但对象不可变，所以在使用体验上很像值类型。
- `Map` 的 key 是否相等，核心取决于 `hashCode()` 和 `equals()`。

## 最容易混淆的点
很多人会把下面两件事混在一起：

1. 方法参数是怎么传进去的
2. `Map` 里 key 是怎么判断相等的

其实它们是两回事。

### 1. 参数传递
Java 里一律是值传递：

- 基础类型：传数值副本
- 引用类型：传引用副本

### 2. Map key 判断
放进 `Map` 之后，是否能被重新找到，看的是：

- `hashCode()`
- `equals()`

不是看“这个对象是不是通过引用传递来的”。

## 什么叫“值传递”
### 基础类型

```java
void change(int x) {
    x = 100;
}
```

如果外面有：

```java
int a = 10;
change(a);
```

那么函数内部拿到的是 `a` 的一个副本。
所以函数里把 `x` 改成 `100`，外面的 `a` 仍然是 `10`。

### 引用类型

```java
void change(Person p) {
    p.age = 20;
}
```

这里传进去的不是整个对象本体，而是“指向这个对象的引用”的副本。

所以：

- 如果通过 `p.age = 20` 去改对象内容
- 外面能看到变化

但如果在方法里写：

```java
p = new Person();
```

那只是让局部变量 `p` 指向了一个新对象，外面的引用并不会跟着变。

这正说明它仍然是值传递，只不过传的是引用值。

## 为什么说 String “像值传递”
`String` 本质上也是引用类型。

但它有两个特点：

1. 不可变
2. 常常重写了 `equals()` 和 `hashCode()`

因此：

- 你改不了原字符串内部内容
- 看起来就像“传进来的是一个不可改的值”

例如：

```java
void change(String s) {
    s = "world";
}
```

外面：

```java
String str = "hello";
change(str);
```

最后 `str` 还是 `"hello"`。

不是因为 `String` 是值类型，而是因为：

- 传进去的是引用副本
- 方法里只是让这个副本重新指向 `"world"`
- 外面的引用没有变

## Map 中的 key 到底看什么
### 基础类型包装类、String 作为 key
像：

- `Integer`
- `Long`
- `String`

这些类型通常都重写了 `equals()` 和 `hashCode()`，
所以两个内容一样的对象，作为 key 时会被认为是同一个逻辑 key。

例如：

```java
Map<String, Integer> map = new HashMap<>();
map.put(new String("abc"), 1);
System.out.println(map.get(new String("abc")));
```

虽然是两个不同的对象，但内容相同，所以可以取到 `1`。

### 自定义对象作为 key
如果自定义类没有正确重写 `equals()` 和 `hashCode()`，
那么 `Map` 默认就会按 `Object` 的实现来判断，
此时更接近“按对象身份区分”。

也就是说：

- 即使两个对象字段值一样
- 也可能被当成两个不同 key

## 为什么可变对象不适合做 HashMap 的 key
如果一个对象作为 key 放进 `HashMap` 后，
你又修改了它参与 `equals()` / `hashCode()` 的字段，
就可能出现：

- put 的时候能放进去
- get 的时候反而拿不出来

因为对象的哈希值和相等性规则已经变了。

所以经验上：

- 不可变对象更适合做 key
- `String` 非常适合做 key

## 典型例子
### 例1：基础类型

```java
int a = 10;
int b = a;
b = 20;
```

此时：

- `a = 10`
- `b = 20`

因为复制的是值本身。

### 例2：引用类型

```java
Person p1 = new Person();
Person p2 = p1;
p2.age = 30;
```

此时：

- `p1.age = 30`
- `p2.age = 30`

因为两个引用都指向同一个对象。

### 例3：String 作为 key

```java
Map<String, Integer> map = new HashMap<>();
map.put("abc", 1);
map.get("abc"); // 能拿到 1
```

因为 `String` 按内容比较，不是按对象地址比较。

## 复杂度
这题更偏概念，不是算法题本身。

但如果放到 `HashMap` 上理解：

- 平均查找复杂度：`O(1)`
- 前提是 `hashCode()` 分布合理，且 `equals()` 定义正确

## 易错点
- “引用类型传参”不等于“引用传递”，Java 里仍然是值传递。
- `String` 不是基础类型，它是引用类型，只是不可变。
- `Map` 的 key 判断，不是看变量名，不是看传参方式，而是看 `equals()` 和 `hashCode()`。
- 可变对象做 key 很危险，尤其是放进去之后再改字段。

## 记忆框架
- Java 只有值传递。
- 基础类型：传值本身。
- 引用类型：传引用副本。
- String：引用类型，但不可变。
- HashMap key：看 `equals()` + `hashCode()`。
