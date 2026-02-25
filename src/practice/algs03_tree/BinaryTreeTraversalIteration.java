package practice.algs03_tree;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

// 不用递归，用迭代的方式实现二叉树的三序遍历
public class BinaryTreeTraversalIteration {

    public static class TreeNode {
        public int val;
        public TreeNode left;
        public TreeNode right;

        public TreeNode(int v) {
            val = v;
        }
    }

    // 先序打印所有节点，非递归版
    public static void preOrder(TreeNode head) {
        if (head != null) {
            Stack<TreeNode> stack = new Stack<>();
            stack.push(head);
            while (!stack.isEmpty()) {
                // 每当弹出一个节点，就打印这个节点
                head = stack.pop();
                System.out.print(head.val + " ");
                // 【注意！！！】先压栈右孩子
                if (head.right != null) {
                    stack.push(head.right);
                }
                // 后压栈左孩子
                if (head.left != null) {
                    stack.push(head.left);
                }
            }
            System.out.println();
        }
    }

    // 中序打印所有节点，非递归版
    public static void inOrder(TreeNode head) {
        // 如果根节点为空，则直接返回，无需遍历
        if (head != null) {
            // 使用栈来模拟递归调用的过程
            Stack<TreeNode> stack = new Stack<>();

            // 当栈不为空或者当前节点不为空时，继续遍历
            while (!stack.isEmpty() || head != null) {
                // 1. 先沿着左子树一路向下，将沿途的所有节点压入栈中
                if (head != null) {
                    stack.push(head); // 将当前节点压入栈
                    head = head.left; // 继续访问左子树
                } else {
                    // 2. 当左子树访问完毕后，弹出栈顶节点并打印其值，然后访问右子树
                    head = stack.pop(); // 弹出栈顶节点
                    System.out.print(head.val + " "); // 打印当前节点的值
                    head = head.right; // 转向右子树
                }
            }

            // 遍历结束后，打印换行符
            System.out.println();
        }
    }

    // 后序打印所有节点，非递归版
    // 这是用两个栈的方法
    public static void posOrderTwoStacks(TreeNode head) {
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

            // 此时 collect 栈中的节点顺序为“根 -> 右 -> 左”，需要逆序输出才能得到后序遍历结果
            while (!collect.isEmpty()) {
                System.out.print(collect.pop().val + " "); // 依次弹出并打印节点值
            }

            // 遍历结束后，打印换行符
            System.out.println();
        }
    }

    // 后序打印所有节点，非递归版
    // 这是用一个栈的方法
    @Deprecated
    public static void posOrderOneStack(TreeNode h) {
        if (h != null) {
            Stack<TreeNode> stack = new Stack<>();
            stack.push(h);
            // 如果始终没有打印过节点，h就一直是头节点
            // 一旦打印过节点，h就变成打印节点
            // 之后h的含义 : 上一次打印的节点
            while (!stack.isEmpty()) {
                TreeNode cur = stack.peek();
                if (cur.left != null && h != cur.left && h != cur.right) {
                    // 有左树且左树没处理过
                    stack.push(cur.left);
                } else if (cur.right != null && h != cur.right) {
                    // 有右树且右树没处理过
                    stack.push(cur.right);
                } else {
                    // 左树、右树 没有 或者 都处理过了
                    System.out.print(cur.val + " ");
                    h = stack.pop();
                }
            }
            System.out.println();
        }
    }

    public static void main(String[] args) {
        TreeNode head = new TreeNode(1);
        head.left = new TreeNode(2);
        head.right = new TreeNode(3);
        head.left.left = new TreeNode(4);
        head.left.right = new TreeNode(5);
        head.right.left = new TreeNode(6);
        head.right.right = new TreeNode(7);
        preOrder(head);
        System.out.println("先序遍历非递归版");
        inOrder(head);
        System.out.println("中序遍历非递归版");
        posOrderTwoStacks(head);
        System.out.println("后序遍历非递归版 - 2个栈实现");
        posOrderOneStack(head);
        System.out.println("后序遍历非递归版 - 1个栈实现");
    }

    // 用一个栈完成先序遍历
    // 测试链接 : https://leetcode.cn/problems/binary-tree-preorder-traversal/
    public static List<Integer> preorderTraversal(TreeNode head) {
        List<Integer> ans = new ArrayList<>();
        if (head != null) {
            Stack<TreeNode> stack = new Stack<>();
            stack.push(head);
            while (!stack.isEmpty()) {
                head = stack.pop();
                ans.add(head.val);
                if (head.right != null) {
                    stack.push(head.right);
                }
                if (head.left != null) {
                    stack.push(head.left);
                }
            }
        }
        return ans;
    }

    // 用一个栈完成中序遍历
    // 测试链接 : https://leetcode.cn/problems/binary-tree-inorder-traversal/
    public static List<Integer> inorderTraversal(TreeNode head) {
        List<Integer> ans = new ArrayList<>();
        if (head != null) {
            Stack<TreeNode> stack = new Stack<>();
            while (!stack.isEmpty() || head != null) {
                if (head != null) {
                    stack.push(head);
                    head = head.left;
                } else {
                    head = stack.pop();
                    ans.add(head.val);
                    head = head.right;
                }
            }
        }
        return ans;
    }

    // 用两个栈完成后序遍历
    // 提交时函数名改为 postorderTraversal
    // 测试链接 : https://leetcode.cn/problems/binary-tree-postorder-traversal/
    public static List<Integer> postorderTraversalTwoStacks(TreeNode head) {
        List<Integer> ans = new ArrayList<>();
        if (head != null) {
            Stack<TreeNode> stack = new Stack<>();
            Stack<TreeNode> collect = new Stack<>();
            stack.push(head);
            while (!stack.isEmpty()) {
                head = stack.pop();
                collect.push(head);
                if (head.left != null) {
                    stack.push(head.left);
                }
                if (head.right != null) {
                    stack.push(head.right);
                }
            }
            while (!collect.isEmpty()) {
                ans.add(collect.pop().val);
            }
        }
        return ans;
    }

    // 用一个栈完成后序遍历
    // 提交时函数名改为postorderTraversal
    // 测试链接 : https://leetcode.cn/problems/binary-tree-postorder-traversal/
    public static List<Integer> postorderTraversalOneStack(TreeNode h) {
        List<Integer> ans = new ArrayList<>();
        if (h != null) {
            Stack<TreeNode> stack = new Stack<>();
            stack.push(h);
            while (!stack.isEmpty()) {
                TreeNode cur = stack.peek();
                if (cur.left != null && h != cur.left && h != cur.right) {
                    stack.push(cur.left);
                } else if (cur.right != null && h != cur.right) {
                    stack.push(cur.right);
                } else {
                    ans.add(cur.val);
                    h = stack.pop();
                }
            }
        }
        return ans;
    }

}
