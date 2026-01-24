package alg.algs002;

import model.ListNode;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/partition-list/">86.分割链表</a>
 * 给你一个链表的头节点 head 和一个特定值 x
 * 请你对链表进行分隔，使得所有 小于 x 的节点都出现在 大于或等于 x 的节点之前。
 * 你应当 保留 两个分区中每个节点的初始相对位置
 */
public class PartitionList {

    public static ListNode partition(ListNode head, int x) {
        if (head == null || head.next == null) {
            return head;
        }
        // 小于x的区域
        ListNode leftHead = null;
        ListNode leftTail = null;
        // 大于等于x的区域
        ListNode rightHead = null;
        ListNode rightTail = null;

        while (head != null) {
            // 小于x
            if (head.val < x) {
                if (leftHead == null) {
                    // 左链表头节点初始化
                    leftHead = head;
                } else {
                    // 将当前节点添加到左链表末尾
                    leftTail.next = head;
                }
                // 左链表尾节点设置为当前节点
                leftTail = head;
            } else {
                // 大于等于x
                if (rightHead == null) {
                    rightHead = head;
                } else {
                    rightTail.next = head;
                }
                rightTail = head;
            }
            // 保存当前节点的下一个节点
            ListNode next = head.next;
            // 【！！！避免形成链表环】断开当前节点与原链表的连接，即 head.next = null
            head.next = null;
            // head 指针移动到下一个节点
            head = next;
        }
        if (leftHead == null) {
            return rightHead;
        } else {
            leftTail.next = rightHead;
            return leftHead;
        }
    }

}
