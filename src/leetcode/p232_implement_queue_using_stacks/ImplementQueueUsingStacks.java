package leetcode.p232_implement_queue_using_stacks;

import java.util.Stack;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/implement-queue-using-stacks/">232.用栈实现队列</a>
 */
public class ImplementQueueUsingStacks {

    public static class MyQueue {
        private Stack<Integer> stack1;
        private Stack<Integer> stack2;

        public MyQueue() {
            stack1 = new Stack<>();
            stack2 = new Stack<>();
        }

        public void push(int x) {
            stack1.push(x);
        }

        public int pop() {
            if (empty()) {
                return -1;
            } else {
                while (!stack1.isEmpty()) {
                    stack2.push(stack1.pop());
                }
                int result = stack2.pop();
                while (!stack2.isEmpty()) {
                    stack1.push(stack2.pop());
                }
                return result;
            }
        }

        public int peek() {
            if (empty()) {
                return -1;
            } else {
                while (!stack1.isEmpty()) {
                    stack2.push(stack1.pop());
                }
                int result = stack2.peek();
                while (!stack2.isEmpty()) {
                    stack1.push(stack2.pop());
                }
                return result;
            }
        }

        public boolean empty() {
            return stack1.isEmpty();
        }
    }

}
