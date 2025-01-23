package alg.algs002;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/reverse-linked-list/">力口-206.反转链表</a>
 * 1、单向链表反转
 * 2、双向链表反转
 * 3、删除链表中指定元素
 */
public class ReverseLinkedList {

    public static void main(String[] args) {

    }

    /**
     * 反转单链表
     * 测试链接 : <a href="https://leetcode.cn/problems/reverse-linked-list/">力口-206.反转链表</a>
     */
    public static ListNode reverseList(ListNode head) {
        if (head == null || head.next == null) {
            return head;
        }
        // 记录当前元素的上一个，及下一个节点
        ListNode pre = null;
        ListNode next;
        while (head != null) {
            // 记录下一个节点
            next = head.next;
            // 将当前节点的next指向pre
            head.next = pre;
            // pre指向当前节点
            pre = head;
            // head指向下一个节点
            head = next;
        }
        return pre;
    }

    /**
     * 递归反转单链表
     *
     * @param head 链表头节点
     * @return 反转后的链表头节点
     */
    public static ListNode reverseListRecursive(ListNode head) {
        // 递归终止条件
        if (head == null || head.next == null) {
            return head;
        }

        // 递归反转剩余部分
        ListNode newHead = reverseListRecursive(head.next);

        // 将当前节点的下一个节点的 next 指向当前节点
        head.next.next = head;
        // 断开当前节点的 next 指针
        head.next = null;

        return newHead;
    }

    public static DoubleListNode reverseDoubleList(DoubleListNode head) {
        if (head == null || head.next == null) {
            return head;
        }
        // 记录当前元素的上一个，及下一个节点
        DoubleListNode pre = null;
        DoubleListNode next;
        while (head != null) {
            // 记录下一个节点
            next = head.next;
            // 将当前节点的next指向pre
            head.next = pre;
            // 将当前节点的pre指向next
            head.pre = next;
            // pre指向当前节点
            pre = head;
            // head指向下一个节点
            head = next;
        }
        return pre;
    }

    public static class ListNode {
        public int val;
        public ListNode next;

        ListNode(int x) {
            val = x;
        }
    }

    public static class DoubleListNode {
        public int val;
        public DoubleListNode pre;
        public DoubleListNode next;

        DoubleListNode(int x) {
            val = x;
        }
    }

}