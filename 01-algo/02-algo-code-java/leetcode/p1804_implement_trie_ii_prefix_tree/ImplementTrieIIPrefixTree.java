package leetcode.p1804_implement_trie_ii_prefix_tree;

import java.util.HashMap;

// 前缀树
// 测试链接 : https://leetcode.cn/problems/implement-trie-ii-prefix-tree/
public class ImplementTrieIIPrefixTree {

    // 路是哈希表实现的
    static class Trie {

        static class TrieNode {
            public int pass;
            public int end;
            // 字符种类多，则使用哈希表替换方法1中的数组
            HashMap<Integer, Trie.TrieNode> nextNodeMap;

            public TrieNode() {
                pass = 0;
                end = 0;
                nextNodeMap = new HashMap<>();
            }
        }

        private final TrieNode root;

        public Trie() {
            root = new Trie.TrieNode();
        }

        public void insert(String word) {
            Trie.TrieNode node = root;
            node.pass++;
            for (int i = 0, path; i < word.length(); i++) { // 从左往右遍历字符
                path = word.charAt(i);
                if (!node.nextNodeMap.containsKey(path)) {
                    node.nextNodeMap.put(path, new Trie.TrieNode());
                }
                node = node.nextNodeMap.get(path);
                node.pass++;
            }
            node.end++;
        }

        public void erase(String word) {
            if (countWordsEqualTo(word) > 0) {
                Trie.TrieNode node = root;
                Trie.TrieNode next;
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
            Trie.TrieNode node = root;
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
            Trie.TrieNode node = root;
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
