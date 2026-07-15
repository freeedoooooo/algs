package leetcode.p622_design_circular_queue;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/design-circular-queue/">622.设计循环队列</a>
 * 设计循环队列
 * MyCircularQueue(k): 构造器，设置队列长度为 k 。
 * Front: 从队首获取元素。如果队列为空，返回 -1 。
 * Rear: 获取队尾元素。如果队列为空，返回 -1 。
 * enQueue(value): 向循环队列插入一个元素。如果成功插入则返回真。
 * deQueue(): 从循环队列中删除一个元素。如果成功删除则返回真。
 * isEmpty(): 检查循环队列是否为空。
 * isFull(): 检查循环队列是否已满。
 */
public class DesignCircularQueue {

    public int[] queue;
    public int head;
    public int tail;
    public int size;
    public int limit;

    public DesignCircularQueue(int n) {
        queue = new int[n];
        head = 0;
        tail = 0;
        size = 0;
        limit = n;
    }

    public boolean enQueue(int value) {
        if (isFull()) {
            return false;
        } else {
            queue[tail] = value;
            tail = (tail + 1 == limit) ? 0 : tail + 1;
            size++;
            return true;
        }
    }

    public boolean deQueue() {
        if (isEmpty()) {
            return false;
        } else {
            queue[head] = 0;
            head = (head + 1 == limit) ? 0 : head + 1;
            size--;
            return true;
        }
    }

    public int Front() {
        if (isEmpty()) {
            return -1;
        } else {
            return queue[head];
        }
    }

    public int Rear() {
        if (isEmpty()) {
            return -1;
        } else {
            int rearIndex = tail == 0 ? limit - 1 : tail - 1;
            return queue[rearIndex];
        }
    }

    public boolean isEmpty() {
        return size == 0;
    }

    public boolean isFull() {
        return size == limit;
    }

}
