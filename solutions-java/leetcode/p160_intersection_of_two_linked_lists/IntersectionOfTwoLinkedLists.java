package leetcode.p160_intersection_of_two_linked_lists;

// 返回两个无环链表相交的第一个节点
// 测试链接 : https://leetcode.cn/problems/intersection-of-two-linked-lists/
public class IntersectionOfTwoLinkedLists {

    // 提交时不要提交这个类
    public static class ListNode {
        public int val;
        public ListNode next;
    }

    // 提交如下的方法
    public static ListNode getIntersectionNode(ListNode h1, ListNode h2) {
        // 如果任一链表为空，则直接返回 null，因为不可能有交点
        if (h1 == null || h2 == null) {
            return null;
        }

        // 定义两个指针 point1 和 point2 分别指向两个链表的头节点
        ListNode point1 = h1;
        ListNode point2 = h2;

        // 计算两个链表的长度差值
        int diff = 0;

        // 遍历链表 h1，计算其长度并移动指针 point1 到链表末尾
        while (point1.next != null) {
            point1 = point1.next;
            diff++;
        }
        // 遍历链表 h2，计算其长度并移动指针 point2 到链表末尾
        while (point2.next != null) {
            point2 = point2.next;
            diff--;
        }
        // 如果两个链表的末尾节点不同，则说明它们没有交点，直接返回 nul
        if (point1 != point2) {
            return null;
        }

        // 根据 diff 的正负值，确定较长的链表是 h1 还是 h2，并重新初始化指针 point1 和 point2
        if (diff >= 0) {
            point1 = h1;
            point2 = h2;
        } else {
            point1 = h2;
            point2 = h1;
        }
        // 取 diff 的绝对值，表示两个链表长度的差值
        diff = Math.abs(diff);

        // 让较长的链表先移动 diff 步，以使两个链表剩余部分的长度相等
        while (diff-- != 0) {
            point1 = point1.next;
        }

        // 同步移动两个指针，直到它们相遇（即找到交点）或到达链表末尾
        while (point1 != point2) {
            point1 = point1.next;
            point2 = point2.next;
        }

        // 返回交点节点（如果没有交点，则此时 point1 和 point2 均为 null）
        return point1;
    }

}
