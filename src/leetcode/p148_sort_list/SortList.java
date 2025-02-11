package leetcode.p148_sort_list;

// 排序链表
// 要求时间复杂度O(N*logN)，额外空间复杂度O(1)，还要求稳定性
// 数组排序做不到，链表排序可以
// 测试链接 : https://leetcode.cn/problems/sort-list/
public class SortList {

    // 不要提交这个类
    public static class ListNode {
        public int val;
        public ListNode next;
    }

    public static ListNode start;

    public static ListNode end;

    // 提交如下的方法
    // 时间复杂度O(N*logN)，额外空间复杂度O(1)，有稳定性
    // 【注意！！！】为了额外空间复杂度O(1)，所以不能使用递归，因为mergeSort递归需要O(log N)的额外空间
    // 自底向上的归并排序（Bottom-up Merge Sort）来实现链表排序。
    // 这种方法避免了递归调用栈的空间开销，因此可以达到额外空间复杂度O(1)的要求。
    public static ListNode sortList(ListNode head) {
        // 计算链表长度
        int n = 0;
        ListNode cur = head;
        while (cur != null) {
            n++;
            cur = cur.next;
        }
        // l1...r1 每组的左部分
        // l2...r2 每组的右部分
        // next 下一组的开头
        // lastTeamEnd 上一组的结尾
        ListNode l1;
        ListNode r1;
        ListNode l2;
        ListNode r2;
        ListNode next;
        ListNode lastTeamEnd;
        // 自底向上归并排序，step初始值为1，每次增大一倍
        for (int step = 1; step < n; step <<= 1) {
            // 第一组很特殊，因为要决定整个链表的头，所以单独处理
            l1 = head;
            r1 = findEnd(l1, step);
            l2 = r1.next;
            r2 = findEnd(l2, step);
            next = r2.next;
            r1.next = null;
            r2.next = null;
            // 合并前两组，每组链表的长度为step
            merge(l1, r1, l2, r2);
            head = start;
            lastTeamEnd = end;
            while (next != null) {
                l1 = next;
                r1 = findEnd(l1, step);
                l2 = r1.next;
                if (l2 == null) {
                    lastTeamEnd.next = l1;
                    break;
                }
                r2 = findEnd(l2, step);
                next = r2.next;
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

    // 包括s在内，往下数k个节点返回
    // 如果不够，返回最后一个数到的非空节点
    public static ListNode findEnd(ListNode s, int k) {
        while (s.next != null && --k != 0) {
            s = s.next;
        }
        return s;
    }

    // l1...r1 -> null : 有序的左部分
    // l2...r2 -> null : 有序的右部分
    // 整体merge在一起，保证有序
    // 并且把全局变量start设置为整体的头，全局变量end设置为整体的尾
    public static void merge(ListNode l1, ListNode r1, ListNode l2, ListNode r2) {
        ListNode pre;
        if (l1.val <= l2.val) {
            start = l1;
            pre = l1;
            l1 = l1.next;
        } else {
            start = l2;
            pre = l2;
            l2 = l2.next;
        }
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) {
                pre.next = l1;
                pre = l1;
                l1 = l1.next;
            } else {
                pre.next = l2;
                pre = l2;
                l2 = l2.next;
            }
        }
        if (l1 != null) {
            pre.next = l1;
            end = r1;
        } else {
            pre.next = l2;
            end = r2;
        }
    }

    // 此方案是一种更优雅的实现，但是使用了递归，空间复杂度不满足O(1)的要求
    public ListNode sortList2(ListNode head) {
        return sortList(head, null);
    }

    public ListNode sortList(ListNode head, ListNode tail) {
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
        ListNode list1 = sortList(head, mid);
        ListNode list2 = sortList(mid, tail);
        ListNode sorted = mergeList(list1, list2);
        return sorted;
    }

    public ListNode mergeList(ListNode node1, ListNode node2) {
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
