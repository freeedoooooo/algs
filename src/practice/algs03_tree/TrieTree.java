package practice.algs03_tree;

import java.util.HashMap;

// 用类描述实现前缀树。不推荐！
// 测试链接 : https://leetcode.cn/problems/implement-trie-ii-prefix-tree/
public class TrieTree {

    // 路是数组实现的
    // 提交时把类名、构造方法改为Trie
    static class Trie1 {

        static class TrieNode {
            public int pass;
            public int end;
            public TrieNode[] nextNodes;

            public TrieNode() {
                pass = 0;
                end = 0;
                // 仅支持26个字母
                nextNodes = new TrieNode[26];
            }
        }

        private final TrieNode root;

        public Trie1() {
            root = new TrieNode();
        }

        // 新加单词
        public void insert(String word) {
            // 每次从根节点开始
            TrieNode node = root;
            node.pass++;
            // 从左往右遍历字符
            for (int i = 0, path; i < word.length(); i++) {
                // 由字符，对应成走向哪条路
                path = word.charAt(i) - 'a';
                if (node.nextNodes[path] == null) {
                    node.nextNodes[path] = new TrieNode();
                }
                node = node.nextNodes[path];
                node.pass++;
            }
            node.end++;
        }

        // 如果之前word插入过前缀树，那么此时删掉一次
        // 如果之前word没有插入过前缀树，那么什么也不做
        public void erase(String word) {
            // 【注意！！！】必须先查询是否已加入过
            if (countWordsEqualTo(word) > 0) {
                TrieNode node = root;
                node.pass--;
                for (int i = 0, path; i < word.length(); i++) {
                    path = word.charAt(i) - 'a';
                    // 【注意！！！】如果该路线 pass=0，说明此节点及之后的节点都删掉了，那么就断掉此路线
                    if (--node.nextNodes[path].pass == 0) {
                        node.nextNodes[path] = null;
                        return;
                    }
                    node = node.nextNodes[path];
                }
                node.end--;
            }
        }

        // 查询前缀树里，word单词出现了几次
        public int countWordsEqualTo(String word) {
            TrieNode node = root;
            for (int i = 0, path; i < word.length(); i++) {
                path = word.charAt(i) - 'a';
                if (node.nextNodes[path] == null) {
                    return 0;
                }
                node = node.nextNodes[path];
            }
            // end 就是全匹配的数量
            return node.end;
        }

        // 查询前缀树里，有多少单词以pre做前缀
        public int countWordsStartingWith(String pre) {
            TrieNode node = root;
            for (int i = 0, path; i < pre.length(); i++) {
                path = pre.charAt(i) - 'a';
                if (node.nextNodes[path] == null) {
                    return 0;
                }
                node = node.nextNodes[path];
            }
            // pass 就是前缀匹配的数量
            return node.pass;
        }
    }

    // 路是哈希表实现的
    // 提交时把类名、构造方法改为Trie
    static class Trie2 {

        static class TrieNode {
            public int pass;
            public int end;
            // 字符种类多，则使用哈希表替换方法1中的数组
            HashMap<Integer, TrieNode> nextNodeMap;

            public TrieNode() {
                pass = 0;
                end = 0;
                nextNodeMap = new HashMap<>();
            }
        }

        private final TrieNode root;

        public Trie2() {
            root = new TrieNode();
        }

        public void insert(String word) {
            TrieNode node = root;
            node.pass++;
            for (int i = 0, path; i < word.length(); i++) { // 从左往右遍历字符
                path = word.charAt(i);
                if (!node.nextNodeMap.containsKey(path)) {
                    node.nextNodeMap.put(path, new TrieNode());
                }
                node = node.nextNodeMap.get(path);
                node.pass++;
            }
            node.end++;
        }

        public void erase(String word) {
            if (countWordsEqualTo(word) > 0) {
                TrieNode node = root;
                TrieNode next;
                node.pass--;
                for (int i = 0, path; i < word.length(); i++) {
                    path = word.charAt(i);
                    next = node.nextNodeMap.get(path);
                    if (--next.pass == 0) {
                        node.nextNodeMap.remove(path);
                        return;
                    }
                    node = next;
                }
                node.end--;
            }
        }

        public int countWordsEqualTo(String word) {
            TrieNode node = root;
            for (int i = 0, path; i < word.length(); i++) {
                path = word.charAt(i);
                if (!node.nextNodeMap.containsKey(path)) {
                    return 0;
                }
                node = node.nextNodeMap.get(path);
            }
            return node.end;
        }

        public int countWordsStartingWith(String pre) {
            TrieNode node = root;
            for (int i = 0, path; i < pre.length(); i++) {
                path = pre.charAt(i);
                if (!node.nextNodeMap.containsKey(path)) {
                    return 0;
                }
                node = node.nextNodeMap.get(path);
            }
            return node.pass;
        }

    }

}
