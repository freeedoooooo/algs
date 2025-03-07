package leetcode.p086_partition_list;

import util.collection.ListNode;

/**
 * 分割链表
 * 测试链接 : https://leetcode.cn/problems/partition-list
 * 给你一个链表的头节点 head 和一个特定值 x
 * 请你对链表进行分隔，使得所有 小于 x 的节点都出现在 大于或等于 x 的节点之前。
 * 你应当 保留 两个分区中每个节点的初始相对位置
 *
 * @author hurui
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
                    // 左链表，未初始化，则先初始化
                    leftHead = head;
                } else {
                    // 左头链表，已初始化，则连接到右链表末尾
                    leftTail.next = head;
                }
                // 左链表尾节点设置为当前节点
                leftTail = head;
            } else {
                // 大于等于x
                if (rightHead == null) {
                    // 右链表，未初始化，则先初始化
                    rightHead = head;
                } else {
                    // 右头链表，已初始化，则连接到右链表末尾
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

        // 可能存在只有右链表的情况
        if (leftHead == null) {
            // 左链表为空，则直接返回右链表
            return rightHead;
        } else {
            // 连接左链表与右链表
            leftTail.next = rightHead;
            return leftHead;
        }
    }

}
