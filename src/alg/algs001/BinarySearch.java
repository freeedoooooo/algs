package alg.algs001;

/**
 * 测试链接：<a href="https://leetcode.cn/problems/find-peak-element/">力扣-162.寻找峰值</a>
 * 二分查找及应用
 * 局部最小（二分的核心思想，是要找到一种排他性的判断标准）
 */
public class BinarySearch {

    public static void main(String[] args) {
        int[] array = {1, 3, 5, 7, 7, 8, 9, 12, 15};
        int binarySearchResult = binarySearch(array, 7);
        System.out.println(binarySearchResult);

        int findLeftResult = findLeft(array, 6);
        System.out.println(findLeftResult);

        int findRightResult = findRight(array, 11);
        System.out.println(findRightResult);
    }


    /**
     * 最基础的二分查找
     */
    public static int binarySearch(int[] arr, int target) {
        if (arr == null || arr.length == 0) {
            return -1;
        }
        int left = 0;
        int right = arr.length - 1;
        while (left <= right) {
            int middle = left + (right - left) / 2;
            if (arr[middle] == target) {
                return middle;
            } else if (arr[middle] > target) {
                right = middle - 1;
            } else {
                left = middle + 1;
            }
        }
        return -1;
    }

    /**
     * 有序数组中找>=num的最左位置
     */
    public static int findLeft(int[] arr, int target) {
        if (arr == null || arr.length == 0) {
            return -1;
        }
        int left = 0;
        int right = arr.length - 1;
        // 记录大于 target 的最左位置
        int index = -1;
        while (left <= right) {
            int middle = left + (right - left) / 2;
            // 如果中间值大于 target，更新 index 并继续在左半部分查找
            if (arr[middle] >= target) {
                right = middle - 1;
                // 记录大于等 target 的最左位置，因为 right 会一直向左移动，当前的 middle 是一个候选位置
                index = middle;
            } else {
                // 如果中间值小于等于 target，继续在右半部分查找
                left = middle + 1;
            }
        }
        return index;
    }

    /**
     * 有序数组中找<=num的最右位置
     */
    public static int findRight(int[] arr, int target) {
        if (arr == null || arr.length == 0) {
            return -1;
        }
        int left = 0;
        int right = arr.length - 1;
        int index = -1;
        while (left <= right) {
            int middle = left + (right - left) / 2;
            if (arr[middle] <= target) {
                left = middle + 1;
                index = middle;
            } else {
                right = middle - 1;
            }
        }
        return index;
    }

    /**
     * 峰值元素是指其值严格大于左右相邻值的元素
     * 给你一个整数数组 nums，已知任何两个相邻的值都不相等
     * 找到峰值元素并返回其索引
     * 数组可能包含多个峰值，在这种情况下，返回 任何一个峰值 所在位置即可。
     * 你可以假设 nums[-1] = nums[n] = 无穷小
     * 你必须实现时间复杂度为 O(log n) 的算法来解决此问题。
     * 测试链接：<a href="https://leetcode.cn/problems/find-peak-element/">力扣-162.寻找峰值</a>
     */
    public static int findPeak(int[] nums) {
        if (nums == null || nums.length == 0) {
            return -1;
        }
        if (nums.length == 1) {
            return 0;
        }
        if (nums[0] > nums[1]) {
            return 0;
        }
        if (nums[nums.length - 1] > nums[nums.length - 2]) {
            return nums.length - 1;
        }
        int left = 1;
        int right = nums.length - 2;
        while (left <= right) {
            int middle = left + (right - left) / 2;
            // 中点就是极大值点
            if (nums[middle] > nums[middle - 1] && nums[middle] > nums[middle + 1]) {
                return middle;
            } else if (nums[middle] > nums[middle - 1]) {
                // 左侧小，右侧大，是增区间，往右找
                left = middle + 1;
            } else {
                // 其他情况，中点是减区间的一点，或者是极小值点，都统一往左找
                right = middle - 1;
            }
        }
        return -1;
    }


}
