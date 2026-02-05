package leetcode.p002_add_two_numbers;

import util.collection.ListNode;

/**
 * 测试链接：<a href="https://leetcode.cn/problems/add-two-numbers/">力扣-2.两数相加</a>
 * 给你两个 非空 的链表，表示两个非负的整数
 * 它们每位数字都是按照 逆序 的方式存储的，并且每个节点只能存储 一位 数字
 * 请你将两个数相加，并以相同形式返回一个表示和的链表。
 * 你可以假设除了数字 0 之外，这两个数都不会以 0 开头
 */
public class AddTwoNumbers {

    public static ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        // 如果其中一个链表为空，直接返回另一个链表
        if (l1 == null) {
            return l2;
        }
        if (l2 == null) {
            return l1;
        }

        // 虚拟头节点，简化边界条件处理
        ListNode head = new ListNode(0);
        // 当前节点，用于构建结果链表
        ListNode current = head;
        // 进位值，初始为 0
        int carry = 0;

        // 遍历两个链表，直到两个链表都遍历完毕
        while (l1 != null || l2 != null) {
            // 获取当前节点的值，如果链表已经遍历完毕，则值为 0
            int value1 = (l1 == null) ? 0 : l1.val;
            int value2 = (l2 == null) ? 0 : l2.val;

            // 计算当前位的和，包括进位
            int sum = value1 + value2 + carry;
            // 计算新的进位
            carry = sum / 10;
            // 当前位的值
            int value = sum % 10;

            // 创建新节点并连接到结果链表
            current.next = new ListNode(value);
            // 移动当前节点
            current = current.next;

            // 移动到下一个节点
            if (l1 != null) {
                l1 = l1.next;
            }
            if (l2 != null) {
                l2 = l2.next;
            }
        }

        // 如果最后还有进位，添加一个新节点到结果链表的末尾
        if (carry != 0) {
            current.next = new ListNode(carry);
        }

        // 返回结果链表的头节点（跳过虚拟头节点）
        return head.next;
    }

}
