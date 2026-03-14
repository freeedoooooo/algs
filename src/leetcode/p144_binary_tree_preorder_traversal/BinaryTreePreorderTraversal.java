package leetcode.p144_binary_tree_preorder_traversal;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

/**
 * 用一个栈完成先序遍历
 * 测试链接 : https://leetcode.cn/problems/binary-tree-preorder-traversal
 *
 * @author Administrator
 */
public class BinaryTreePreorderTraversal {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    /**
     * 先序遍历
     * 先压栈右孩子，后压栈左孩子；
     * 左孩子先出栈，再循环上一步。
     */
    public static List<Integer> preorderTraversal(TreeNode head) {
        // 收集打印的结果
        List<Integer> result = new ArrayList<>();
        if (head == null) {
            return result;
        }

        Stack<TreeNode> stack = new Stack<>();
        // 先压栈头节点
        stack.push(head);

        while (!stack.isEmpty()) {
            // 每当弹出一个节点，就打印这个节点
            head = stack.pop();
            result.add(head.val);

            // 【注意！！！】先压栈右孩子，后出栈
            if (head.right != null) {
                stack.push(head.right);
            }

            // 后压栈左孩子，所以会先出栈
            if (head.left != null) {
                stack.push(head.left);
            }
        }

        return result;
    }

}
