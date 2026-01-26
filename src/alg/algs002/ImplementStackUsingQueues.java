package alg.algs002;

import java.util.LinkedList;
import java.util.Queue;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/implement-stack-using-queues//">225.用队列实现栈</a>
 */
public class ImplementStackUsingQueues {

    public static class MyStack {
        private Queue<Integer> queue;

        public MyStack() {
            queue = new LinkedList<>();
        }

        public void push(int x) {
            // 重排队头到x之前的元素，依次挪到x之后，保持与栈的顺序一致
            int n = queue.size();
            // 入栈元素放到队列尾
            queue.offer(x);
            for (int i = 0; i < n; i++) {
                queue.offer(queue.poll());
            }
        }

        public int pop() {
            // 弹出栈顶，与取出队头元素一致
            return queue.poll();
        }

        public int top() {
            return queue.peek();
        }

        public boolean empty() {
            return queue.isEmpty();
        }
    }

}
