package leetcode.p148_sort_list;

/**
 * 排序链表
 * 要求时间复杂度O(N*logN)，额外空间复杂度O(1)，还要求稳定性
 * 数组排序做不到，链表排序可以
 * 测试链接 : https://leetcode.cn/problems/sort-list
 *
 * @author Administrator
 */
public class SortList {

    public static class ListNode {
        public int val;
        public ListNode next;
    }

    public static ListNode start;
    public static ListNode end;

    /**
     * 时间复杂度为 O(N*logN)，额外空间复杂度 O(1)，有稳定性
     * 【注意！！！】为了额外空间复杂度O(1)，所以不能使用递归，因为mergeSort递归需要O(log N)的额外空间
     * 自底向上的归并排序（Bottom-up Merge Sort）来实现链表排序。
     * 这种方法避免了递归调用栈的空间开销，因此可以达到额外空间复杂度O(1)的要求。
     */
    public static ListNode sortList(ListNode head) {
        // 计算链表长度
        int n = 0;
        ListNode cur = head;
        while (cur != null) {
            n++;
            cur = cur.next;
        }

        // l1...r1 每组的左半区
        // l2...r2 每组的右半区
        ListNode l1;
        ListNode r1;
        ListNode l2;
        ListNode r2;

        // nextTeamHead 下一组的开头
        ListNode nextTeamHead;
        // lastTeamEnd 上一组的结尾
        ListNode lastTeamEnd;

        // 自底向上归并排序，step初始值为1，每次增大一倍
        for (int step = 1; step < n; step <<= 1) {
            // 【注意！！！】第一次组的2个半区合并很特殊，因为要决定整个链表的头，所以单独处理
            // 左半区的左边界，就是头节点
            l1 = head;
            // 找到左半区的右边界
            r1 = findEnd(l1, step);

            // 右半区的左边界，就是左半区的右边界
            l2 = r1.next;
            // 找到右半区的右边界
            r2 = findEnd(l2, step);

            // 下一组的头节点
            nextTeamHead = r2.next;

            // 【注意！！！】断开右边界的指针，否则会成环
            r1.next = null;
            r2.next = null;
            // 合并左、右半区，每半区链表的长度为step，并更新全局变量 start & end
            merge(l1, r1, l2, r2);

            head = start;
            lastTeamEnd = end;

            // TODO: 2025/2/17  
            while (nextTeamHead != null) {
                l1 = nextTeamHead;
                r1 = findEnd(l1, step);
                l2 = r1.next;
                if (l2 == null) {
                    // 若右半区为空，则将左半区接到整体链表的尾部
                    lastTeamEnd.next = l1;
                    break;
                }
                r2 = findEnd(l2, step);
                nextTeamHead = r2.next;
                r1.next = null;
                r2.next = null;
                // 依次合并第[3 & 4]、[5 & 6]...组
                merge(l1, r1, l2, r2);
                lastTeamEnd.next = start;
                lastTeamEnd = end;
            }
        }
        return head;
    }

    /**
     * 返回k步之后的节点
     * 包括s在内，往下数k个节点返回
     * 如果不够，返回最后一个数到的非空节点
     */
    public static ListNode findEnd(ListNode s, int k) {
        while (s.next != null && --k != 0) {
            s = s.next;
        }
        return s;
    }

    /**
     * 合并两个有序链表，得到一个有序链表。
     * l1...r1 -> null : 有序的左半区
     * l2...r2 -> null : 有序的右半区
     * 整体merge在一起，保证有序
     * 并且把全局变量start设置为整体的头，全局变量end设置为整体的尾
     */
    public static void merge(ListNode l1, ListNode r1, ListNode l2, ListNode r2) {
        ListNode pre;
        // 先确定头节点
        if (l1.val <= l2.val) {
            start = l1;
            pre = l1;
            l1 = l1.next;
        } else {
            start = l2;
            pre = l2;
            l2 = l2.next;
        }

        // 遍历，直到某一个链表遍历完
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) {
                // 左半区的节点，继续往下走
                pre.next = l1;
                pre = l1;
                l1 = l1.next;
            } else {
                // 右半区的节点，继续往下走
                pre.next = l2;
                pre = l2;
                l2 = l2.next;
            }
        }

        // 遍历完，剩下的链表，直接拼接上即可
        if (l1 != null) {
            pre.next = l1;
            end = r1;
        } else {
            pre.next = l2;
            end = r2;
        }
    }

    /**
     * 此方案是一种逻辑更优雅地实现，但是使用了递归，空间复杂度不满足O(1)的要求
     */
    public ListNode sortList2(ListNode head) {
        return sortListRecursion(head, null);
    }

    public ListNode sortListRecursion(ListNode head, ListNode tail) {
        if (head == null) {
            return head;
        }
        if (head.next == tail) {
            head.next = null;
            return head;
        }
        // 切分
        ListNode slow = head;
        ListNode fast = head;
        while (fast != tail) {
            fast = fast.next;
            slow = slow.next;
            if (fast != tail) {
                fast = fast.next;
            }
        }

        ListNode mid = slow;
        ListNode list1 = sortListRecursion(head, mid);
        ListNode list2 = sortListRecursion(mid, tail);
        ListNode sorted = mergeListRecursion(list1, list2);
        return sorted;
    }

    public ListNode mergeListRecursion(ListNode node1, ListNode node2) {
        ListNode newHead = new ListNode();
        ListNode tmp = newHead;
        ListNode tmp1 = node1;
        ListNode tmp2 = node2;
        while (tmp1 != null && tmp2 != null) {
            if (tmp1.val <= tmp2.val) {
                tmp.next = tmp1;
                tmp1 = tmp1.next;
            } else {
                tmp.next = tmp2;
                tmp2 = tmp2.next;
            }
            tmp = tmp.next;
        }
        if (tmp1 != null) {
            tmp.next = tmp1;
        } else if (tmp2 != null) {
            tmp.next = tmp2;
        }
        return newHead.next;
    }

}
