package leetcode;

import util.collection.ListNode;

/**
 * 测试链接 : <a href="https://leetcode.cn/problems/merge-two-sorted-lists/">力扣-21.合并两个有序链表</a>
 */
public class MergeTwoSortedLists {

    public static ListNode mergeTwoListsRecursive(ListNode list1, ListNode list2) {
        if (list1 == null) {
            return list2;
        }
        if (list2 == null) {
            return list1;
        }
        if (list1.val < list2.val) {
            list1.next = mergeTwoListsRecursive(list1.next, list2);
            return list1;
        } else {
            list2.next = mergeTwoListsRecursive(list1, list2.next);
            return list2;
        }
    }

    public static ListNode mergeTwoLists(ListNode list1, ListNode list2) {
        // 如果其中一个链表为空，直接返回另一个链表
        if (list1 == null) {
            return list2;
        }
        if (list2 == null) {
            return list1;
        }

        // 确定合并后链表的头节点
        ListNode head = list1.val < list2.val ? list1 : list2;

        // 第一个指针，指向 head 所在链表的下一个节点
        ListNode cur1 = head.next;

        // 第二个指针，指向未合并链表的下一个节点
        ListNode cur2 = head == list1 ? list2 : list1;

        // 上一个节点，初始为 head
        ListNode pre = head;

        // 遍历两个链表，逐个比较节点值
        while (cur1 != null && cur2 != null) {
            if (cur1.val < cur2.val) {
                // 如果 cur1 的值较小，将其连接到 pre 的后面
                pre.next = cur1;
                cur1 = cur1.next;
            } else {
                // 如果 cur2 的值较小，将其连接到 pre 的后面
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
