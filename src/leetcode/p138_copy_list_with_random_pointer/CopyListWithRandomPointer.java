package leetcode.p138_copy_list_with_random_pointer;

// 复制带随机指针的链表
// 测试链接 : https://leetcode.cn/problems/copy-list-with-random-pointer/
public class CopyListWithRandomPointer {

    // 不要提交这个类
    public static class Node {
        public int val;
        public Node next;
        public Node random;

        public Node(int v) {
            val = v;
        }
    }

    // 提交如下的方法
    // 遍历了三次：
    // 1、拷贝节点
    // 2、设置新节点的random指针
    // 3、分离拷贝出的新链表
    public static Node copyRandomList(Node head) {
        if (head == null) {
            return null;
        }
        Node cur = head;
        Node next = null;
        // 【第一次遍历】先拷贝节点，插入到原节点之后，等效形成了一个哈希表映射
        // 不使用额外的哈希表保存拷贝节点的映射，确保空间复杂度为O(1)
        // 1 -> 2 -> 3 -> ...
        // 变成 : 1 -> 1' -> 2 -> 2' -> 3 -> 3' -> ...
        while (cur != null) {
            next = cur.next;
            cur.next = new Node(cur.val);
            cur.next.next = next;
            cur = next;
        }
        cur = head;
        Node copy = null;
        // 【第二次遍历】利用上面新老节点的结构关系，设置每一个新节点的random指针
        while (cur != null) {
            // 因为插入了拷贝出来的新节点，所以以此跳2步
            next = cur.next.next;
            // 拷贝节点，紧跟在当前节点之后
            copy = cur.next;
            if (cur.random != null) {
                // 拷贝出的节点的random指针，指向原节点的random指针的下一个节点，也是其拷贝出的新节点
                copy.random = cur.random.next;
            } else {
                copy.random = null;
            }
            cur = next;
        }
        // 返回值是原头节点对应的拷贝节点，就是拷贝出链表的头节点
        Node result = head.next;
        cur = head;
        // 【第三次遍历】新老链表分离 : 老链表重新连在一起，新链表重新连在一起
        while (cur != null) {
            next = cur.next.next;
            copy = cur.next;
            cur.next = next;
            copy.next = next != null ? next.next : null;
            cur = next;
        }
        // 返回新链表的头节点
        return result;
    }

}
