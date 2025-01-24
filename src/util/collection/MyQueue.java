package util.collection;

/**
 * 队列，由数组实现，必须限制数据量
 */
public class MyQueue {

    public int[] queue;
    // 队头
    public int l;
    // 队尾
    public int r;

    public MyQueue(int size) {
        this.queue = new int[size];
        this.l = 0;
        this.r = 0;
    }

    /**
     * 从队尾加
     */
    public void offer(int num) {
        queue[r++] = num;
    }

    /**
     * 从队头拿
     */
    public int poll() {
        return queue[l++];
    }

    /**
     * 返回队头元素，不出队
     */
    public int head() {
        return queue[l];
    }

    /**
     * 返回队尾元素，不出队
     */
    public int tail() {
        return queue[r - 1];
    }

    public boolean isEmpty() {
        return this.l == this.r;
    }

    public int size() {
        return this.r - this.l;
    }

}
