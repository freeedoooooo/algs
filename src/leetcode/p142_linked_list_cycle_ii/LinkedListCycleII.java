package leetcode.p142_linked_list_cycle_ii;

// 返回链表的第一个入环节点
// 测试链接 : https://leetcode.cn/problems/linked-list-cycle-ii/
public class LinkedListCycleII {

    // 不要提交这个类
    public static class ListNode {
        public int val;
        public ListNode next;
    }

    // 提交如下的方法
    // 快慢指针，思路有点像追击问题

    /**
     * 快慢指针,慢指针每次一步，快指针每次两步
     * 由题可知：两个指针相遇一定是在环内，相遇时的慢指针一定未走完一环
     * 快指针已经走完k环
     * 设：从头结点到入环点的距离为a，入环点到相遇点的距离为b，
     * 相遇点到入环点的距离为c；【环长】即为 b + c
     * 所以：慢指针走的路程：a + b
     * 快指针走的路程：a + b + k * (b + c)
     * 又因为快指针的速度是慢指针的两倍,那么时间相同时，路程也是两倍
     * 所以：2 * (a + b) = a + b + k * (b + c) =>
     * a + a + b + b = a + b + b + c + (k - 1) * (b + c) =>
     * a = c + (k - 1) * (b + c)
     * 即：从头结点到入环点的距离，等于从相遇点到入环点的距离c，加上k-1倍环长距离
     * 当快慢指针相遇时，让头结点与慢指针同时向后一步步走
     * 那么两个指针一定会在入环点相遇
     */
    public static ListNode detectCycle(ListNode head) {
        if (head == null || head.next == null || head.next.next == null) {
            return null;
        }
        ListNode slow = head.next;
        ListNode fast = head.next.next;
        // 第一阶段，判断是否有环
        // 当有环时，快慢指针必定会相遇
        while (slow != fast) {
            // 如果遇到终点，则必定无环
            if (fast.next == null || fast.next.next == null) {
                return null;
            }
            slow = slow.next;
            fast = fast.next.next;
        }
        // 第二阶段：找到环的起始节点
        // 将快指针重新指向链表头节点
        fast = head;
        while (slow != fast) {
            // 快、慢指针，都改为移动一步，再次相遇的节点就是入环节点
            slow = slow.next;
            fast = fast.next;
        }
        return slow;
    }

}
