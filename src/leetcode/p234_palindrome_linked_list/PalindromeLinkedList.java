package leetcode.p234_palindrome_linked_list;

// 判断链表是否是回文结构
// 测试链接 : https://leetcode.cn/problems/palindrome-linked-list/
public class PalindromeLinkedList {

    // 不需要提交这个类
    public static class ListNode {
        public int val;
        public ListNode next;
    }

    // 仅需要提交此方法
    public static boolean isPalindrome(ListNode head) {
        if (head == null || head.next == null) {
            return true;
        }
        ListNode slow = head;
        ListNode fast = head;
        // 找中点
        // 偶数个节点时，slow指向中点前一个节点
        // 奇数个节点时，slow指向中点节点
        while (fast.next != null && fast.next.next != null) {
            slow = slow.next;
            fast = fast.next.next;
        }
        // 现在中点就是slow，从中点开始往后的节点逆序
        ListNode pre = slow;
        ListNode cur = slow.next;
        ListNode next = null;
        // 【注意！！！此步骤的目的是，避免形成循环链表】
        slow.next = null;
        while (cur != null) {
            next = cur.next;
            cur.next = pre;
            pre = cur;
            cur = next;
        }
        // 上面的过程已经把链表调整成从左右两侧往中间指，slow.next=null
        // head -> ... -> slow <- ... <- pre
        boolean result = true;
        ListNode left = head;
        ListNode right = pre;
        // left往右、right往左，每一步比对值是否一样，如果某一步不一样答案就是false
        while (left != null && right != null) {
            if (left.val != right.val) {
                result = false;
                break;
            }
            left = left.next;
            right = right.next;
        }
        // 把链表调整回原来的样子，再返回判断结果
        cur = pre.next;
        pre.next = null;
        next = null;
        while (cur != null) {
            next = cur.next;
            cur.next = pre;
            pre = cur;
            cur = next;
        }
        return result;
    }

}
