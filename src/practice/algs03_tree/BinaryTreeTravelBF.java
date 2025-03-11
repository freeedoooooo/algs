package practice.algs03_tree;

import java.util.LinkedList;
import java.util.Queue;

/**
 * 二叉树的广度优先遍历
 */
public class BinaryTreeTravelBF {

    // 计算二叉树的最大宽度
    public static int maxWidth(TreeNode root) {
        if (root == null) {
            return 0;
        }

        // 使用队列进行广度优先遍历
        Queue<TreeNode> queue = new LinkedList<>();
        // 将根节点加入队列
        queue.offer(root);

        // 记录最大宽度
        int maxWidth = 0;

        while (!queue.isEmpty()) {
            // 当前层的节点数
            int levelSize = queue.size();
            // 更新最大宽度
            maxWidth = Math.max(maxWidth, levelSize);

            // 遍历当前层的所有节点
            for (int i = 0; i < levelSize; i++) {
                // 取出当前节点
                TreeNode currentNode = queue.poll();
                // 将当前节点的左右子节点加入队列
                if (currentNode.left != null) {
                    queue.offer(currentNode.left);
                }
                if (currentNode.right != null) {
                    queue.offer(currentNode.right);
                }
            }
        }

        return maxWidth;
    }

    // https://leetcode.cn/problems/maximum-width-of-binary-tree/description/
    public int widthOfBinaryTree(TreeNode root) {
        // todo 需要计算中间null节点的数量
        return 0;
    }

    // 测试代码
    public static void main(String[] args) {
        /*
        构造一个二叉树：
              1
             / \
            2   3
           / \   \
          4   5   6
         */
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2);
        root.right = new TreeNode(3);
        root.left.left = new TreeNode(4);
        root.left.right = new TreeNode(5);
        root.right.right = new TreeNode(6);

        int width = maxWidth(root);
        System.out.println("二叉树的最大宽度是: " + width); // 输出: 3
    }

}


// 定义二叉树节点类
class TreeNode {
    int val;
    TreeNode left;
    TreeNode right;

    TreeNode(int val) {
        this.val = val;
        this.left = null;
        this.right = null;
    }
}
