package leetcode.p144_binary_tree_preorder_traversal;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

// 用一个栈完成先序遍历
// 测试链接 : https://leetcode.cn/problems/binary-tree-preorder-traversal/
public class BinaryTreePreorderTraversal {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    public static List<Integer> preorderTraversal(TreeNode head) {
        List<Integer> result = new ArrayList<>();
        if (head != null) {
            Stack<TreeNode> stack = new Stack<>();
            stack.push(head);
            while (!stack.isEmpty()) {
                // 每当弹出一个节点，就打印这个节点
                head = stack.pop();
                result.add(head.val);
                // 【注意！！！】先压栈右孩子
                if (head.right != null) {
                    stack.push(head.right);
                }
                // 后压栈左孩子
                if (head.left != null) {
                    stack.push(head.left);
                }
            }
        }
        return result;
    }

}
