package leetcode.p021_merge_two_sorted_lists;

import util.collection.ListNode;

/**
 * 合并两个有序链表
 * 测试链接 : https://leetcode.cn/problems/merge-two-sorted-lists
 *
 * @author hurui
 */
public class MergeTwoSortedLists {

    /**
     * 方法1，递归实现
     */
    public static ListNode mergeTwoListsRecursive(ListNode head1, ListNode head2) {
        if (head1 == null) {
            return head2;
        }
        if (head2 == null) {
            return head1;
        }
        // 先确定头节点，较小的值作为头节点，就是最终要返回的结果
        if (head1.val < head2.val) {
            // 头节点较小的链表，后面的链表与另一个链表合并
            // 将较小值节点连接到结果链表的后面，并移动指针
            head1.next = mergeTwoListsRecursive(head1.next, head2);
            return head1;
        } else {
            head2.next = mergeTwoListsRecursive(head1, head2.next);
            return head2;
        }
    }

    /**
     * 方法2，遍历列表
     */
    public static ListNode mergeTwoLists(ListNode head1, ListNode head2) {
        // 如果其中一个链表为空，直接返回另一个链表
        if (head1 == null) {
            return head2;
        }
        if (head2 == null) {
            return head1;
        }

        // 确定合并后链表的头节点
        ListNode head = head1.val < head2.val ? head1 : head2;

        // 第一个指针，指向 head 所在链表的下一个节点
        ListNode cur1 = head.next;

        // 第二个指针，指向未合并链表的下一个节点
        ListNode cur2 = head == head1 ? head2 : head1;

        // 上一个节点，初始为 head
        ListNode pre = head;

        // 遍历两个链表，逐个比较节点值
        while (cur1 != null && cur2 != null) {
            if (cur1.val < cur2.val) {
                // 如果 cur1 的值较小，将其连接到 pre 的后面，指针 cur2 保持不变
                pre.next = cur1;
                cur1 = cur1.next;
            } else {
                // 如果 cur2 的值较小，将其连接到 pre 的后面，指针 cur1 保持不变
                pre.next = cur2;
                cur2 = cur2.next;
            }
            // 移动 pre 到新连接的节点
            pre = pre.next;
        }

        // 将剩余的链表直接连接到 pre 的后面
        pre.next = cur1 != null ? cur1 : cur2;

        // 返回合并后的链表头节点
        return head;
    }

}
