package util.collection;

/**
 * 栈，由数组实现，必须限制数量
 */
public class MyStack {

    public int[] stack;

    // 栈，只需要队头指针，所以只需要一个变量size
    public int size;

    public MyStack(int size) {
        this.size = size;
        this.stack = new int[size];
    }

    // 压栈
    public void push(int num) {
        stack[size++] = num;
    }

    // 出栈
    public int pop() {
        return stack[--size];
    }

    // 返回栈顶元素
    public int peek() {
        return stack[size - 1];
    }

    public boolean isEmpty() {
        return size == 0;
    }

    public int size() {
        return size;
    }

}
