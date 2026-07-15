package leetcode.p145_binary_tree_postorder_traversal;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

/**
 * 用两个栈完成后序遍历
 * 测试链接 : https://leetcode.cn/problems/binary-tree-postorder-traversal
 *
 * @author Administrator
 */
public class BinaryTreePostorderTraversal {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    /**
     * 后序遍历所有节点，非递归版
     * 这是用两个栈的方法
     * 后序遍历，借鉴先序遍历的思路，先序遍历的压栈顺序是“根 -> 右 -> 左”，与后续遍历的顺序正好逆序；
     * 因此，我们只需要按照先序遍历的顺序，将打印节点时的操作改为压入另一个 stack，然后此 stack 出栈的顺序，即可得到后序遍历的结果。
     */
    public static List<Integer> postorderTraversal(TreeNode head) {
        List<Integer> result = new ArrayList<>();
        // 如果根节点为空，则直接返回，无需遍历
        if (head == null) {
            return result;
        }

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

            // 【注意！！！】先将左子树压入 stack（在先序遍历中，此处是先压入右孩子）
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

        return result;
    }

}
