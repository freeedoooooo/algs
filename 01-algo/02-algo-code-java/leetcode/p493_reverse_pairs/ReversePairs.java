package leetcode.p493_reverse_pairs;

import java.util.Arrays;

// 493.翻转对
// 测试链接 : https://leetcode.cn/problems/reverse-pairs/
// 补充：小和问题
// 测试链接 : https://www.nowcoder.com/practice/edfe05a1d45c4ea89101d936cac32469
// 例如，数组 s = [1, 3, 5, 2, 4, 6] ，
// 在 s[0] 的左边小于或等于 s[0] 的数的和为 0 ；
// 在 s[1] 的左边小于或等于 s[1] 的数的和为 1 ；
// 在 s[2] 的左边小于或等于 s[2] 的数的和为 1+3=4 ；
// 在 s[3] 的左边小于或等于 s[3] 的数的和为 1 ；
// 在 s[4] 的左边小于或等于 s[4] 的数的和为 1+3+2=6 ；
// 在 s[5] 的左边小于或等于 s[5] 的数的和为 1+3+5+2+4=15 。
// 所以 s 的小和为 0+1+4+1+6+15=27
// 给定一个数组 s ，实现函数返回 s 的小和
public class ReversePairs {

    public static int[] temp = new int[50001];

    public static void main(String[] args) {
        int[] arr = {1, 3, 5, 2, 4, 6};
        long sum = smallSum(arr, 0, arr.length - 1);
        System.out.println("small sum = " + sum);
    }

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
        return count(nums, l, m) + count(nums, m + 1, r) + mergeCount(nums, l, m, r);
    }

    public static int mergeCount(int[] arr, int l, int m, int r) {
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

    public static long smallSum(int[] arr, int l, int r) {
        if (l == r) {
            return 0;
        }
        int m = (l + r) / 2;
        return smallSum(arr, l, m) + smallSum(arr, m + 1, r) + mergeSmallSum(arr, l, m, r);
    }

    public static long mergeSmallSum(int[] arr, int l, int m, int r) {
        System.out.println("tmp l = " + l);
        System.out.println("tmp m = " + m);
        System.out.println("tmp r = " + r);
        System.out.println("tmp arr = " + Arrays.toString(arr));
        // 统计求和
//        long totalSum = 0;
//        // 从右往左看，即先遍历右侧半区，遇到左半区的值小于等于右侧半区的值，则统计左侧半区的值之和
//        for (int j = m + 1; j <= r; j++) {
//            // 【注意！！！】此处要重新从 l 开始遍历，好理解
//            // 其实可以优化，因为 arr[j] 大于左侧的累加，必定是从 arr[i+1] 开始，并包括 arr[l] 到 arr[i] 的小和
//            int i = l;
//            while (i <= m && arr[i] <= arr[j]) {
//                totalSum += arr[i++];
//            }
//        }

        // 【改进版】
        long totalSum = 0;
        long sum = 0;
        // 从右往左看，即先遍历右侧半区，遇到左半区的值小于等于右侧半区的值，则统计左侧半区的值之和
        for (int j = m + 1; j <= r; j++) {
            int i = l;
            while (i <= m && arr[i] <= arr[j]) {
                // 【注意！！！】此处的 i 直接往后移动，因为两边分区都已经是有序数组了
                // 并且 arr[j] 小和的起点是 arr[j-1] 的小和
                sum += arr[i++];
            }
            totalSum = totalSum + sum;
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
        System.out.println("--- tmp sum = " + sum);
        return sum;
    }

}
