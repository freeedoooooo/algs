package leetcode.p094_binary_tree_inorder_traversal;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

/**
 * 用一个栈完成中序遍历
 * 测试链接 : https://leetcode.cn/problems/binary-tree-inorder-traversal
 *
 * @author hurui
 */
public class BinaryTreeInorderTraversal {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    public static List<Integer> inorderTraversal(TreeNode head) {
        // 存储中序遍历结果的列表
        List<Integer> result = new ArrayList<>();
        // 如果根节点为空，则直接返回，无需遍历
        if (head != null) {
            // 使用栈来模拟递归调用的过程
            Stack<TreeNode> stack = new Stack<>();
            // 当栈不为空或者当前节点不为空时，继续遍历
            while (!stack.isEmpty() || head != null) {
                // 1. 先沿着左子树一路向下，将沿途的所有节点压入栈中
                if (head != null) {
                    // 将当前节点压入栈
                    stack.push(head);
                    // 继续访问左子树
                    head = head.left;
                } else {
                    // 2. 当左子树访问完毕后，弹出栈顶节点并打印其值，然后访问右子树
                    // 弹出栈顶节点
                    head = stack.pop();
                    // 【打印】当前节点的值
                    result.add(head.val);
                    // 转向右子树，如果右节点为空，则 while 的下一次循环，依然会继续弹栈
                    head = head.right;
                }
            }
        }
        return result;
    }

}
