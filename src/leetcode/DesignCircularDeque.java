package leetcode;

// 设计循环双端队列
// 测试链接 : https://leetcode.cn/problems/design-circular-deque/
public class DesignCircularDeque {

    public int[] queue;
    public int head;
    public int tail;
    public int size;
    public int limit;

    public DesignCircularDeque(int n) {
        queue = new int[n];
        head = 0;
        tail = 0;
        size = 0;
        limit = n;
    }

    public boolean insertFront(int value) {
        if (isFull()) {
            return false;
        } else {
            if (isEmpty()) {
                queue[0] = value;
                // 【！！！注意此处要重置 head & tail 指针的位置】
                head = tail = 0;
            } else {
                head = (head == 0) ? limit - 1 : head - 1;
                queue[head] = value;
            }
            size++;
            return true;
        }
    }

    public boolean insertLast(int value) {
        if (isFull()) {
            return false;
        } else {
            if (isEmpty()) {
                queue[0] = value;
                // 【！！！注意此处要重置 head & tail 指针的位置】
                head = tail = 0;
            } else {
                tail = (tail + 1 == limit) ? 0 : tail + 1;
                queue[tail] = value;
            }
            size++;
            return true;
        }
    }

    public boolean deleteFront() {
        if (isEmpty()) {
            return false;
        } else {
            queue[head] = 0;
            head = (head + 1 == limit) ? 0 : head + 1;
            size--;
            return true;
        }
    }

    public boolean deleteLast() {
        if (isEmpty()) {
            return false;
        } else {
            queue[tail] = 0;
            tail = (tail == 0) ? limit - 1 : tail - 1;
            size--;
            return true;
        }
    }

    public int getFront() {
        if (isEmpty()) {
            return -1;
        } else {
            return queue[head];
        }
    }

    public int getRear() {
        if (isEmpty()) {
            return -1;
        } else {
            return queue[tail];
        }
    }

    public boolean isEmpty() {
        return size == 0;
    }

    public boolean isFull() {
        return size == limit;
    }

}
