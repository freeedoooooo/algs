package leetcode;

// 493.翻转对
// 测试链接 : https://leetcode.cn/problems/reverse-pairs/
public class ReversePairs {

    public static int[] temp = new int[50001];

    public static int reversePairs(int[] nums) {
        if (nums == null || nums.length < 2) {
            return 0;
        }
        return count(nums, 0, nums.length - 1);
    }

    public static int count(int[] nums, int l, int r) {
        if (l == r) {
            return 0;
        }
        int m = l + (r - l) / 2;
        // 递归统计左半部分和右半部分的翻转对数量，并加上合并时的翻转对数量
        return count(nums, l, m) + count(nums, m + 1, r) + merge(nums, l, m, r);
    }

    public static int merge(int[] arr, int l, int m, int r) {
        // 统计部分
        int count = 0;
        for (int i = l, j = m + 1; i <= m; i++) {
            // 遍历左半部分，找到满足 arr[i] > 2 * arr[j] 的 j 的范围
            while (j <= r && (long) arr[i] > (long) arr[j] * 2) {
                j++;
            }
            count += j - m - 1;
        }
        // 正常merge
        int index = l;
        int left = l;
        int right = m + 1;
        while (left <= m && right <= r) {
            temp[index++] = arr[left] <= arr[right] ? arr[left++] : arr[right++];
        }
        while (left <= m) {
            temp[index++] = arr[left++];
        }
        while (right <= r) {
            temp[index++] = arr[right++];
        }
        for (index = l; index <= r; index++) {
            arr[index] = temp[index];
        }
        return count;
    }

}
