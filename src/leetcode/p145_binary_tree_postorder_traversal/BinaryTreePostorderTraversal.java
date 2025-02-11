package leetcode.p145_binary_tree_postorder_traversal;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

// 用一个栈完成先序遍历
// 测试链接 : https://leetcode.cn/problems/binary-tree-preorder-traversal/
public class BinaryTreePostorderTraversal {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    // 后序遍历所有节点，非递归版
    // 这是用两个栈的方法
    public static List<Integer> postorderTraversal(TreeNode head) {
        List<Integer> result = new ArrayList<>();
        // 如果根节点为空，则直接返回，无需遍历
        if (head != null) {
            // 定义两个栈：
            // stack 用于模拟递归调用过程，按“根 -> 右 -> 左”的顺序压入节点。
            // collect 用于收集后序遍历的结果，最终需要逆序输出。
            Stack<TreeNode> stack = new Stack<>();
            Stack<TreeNode> collect = new Stack<>();

            // 将根节点压入 stack，开始遍历
            stack.push(head);

            // 当 stack 不为空时，继续处理
            while (!stack.isEmpty()) {
                // 弹出 stack 的栈顶节点
                head = stack.pop();
                // 【注意！！！】将当前节点压入 collect 栈中
                collect.push(head);

                // 【注意！！！】先将左子树压入 stack（先序遍历，此处是先右）
                if (head.left != null) {
                    stack.push(head.left);
                }

                // 再将右子树压入 stack
                if (head.right != null) {
                    stack.push(head.right);
                }
            }

            // 【注意！！！】此时 collect 栈中的节点顺序为“根 -> 右 -> 左”，需要逆序输出才能得到后序遍历结果
            while (!collect.isEmpty()) {
                // 依次弹出节点值
                result.add(collect.pop().val);
            }
        }
        return result;
    }

}
