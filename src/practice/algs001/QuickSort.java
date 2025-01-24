package practice.algs001;

import util.MyArrayUtil;

/**
 * 快速排序
 * 【推荐】荷兰国旗问题
 */
public class QuickSort {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArray(5000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        InsertionSort.insertionSort(arr1);
        sortArray(arr2);

        boolean isEqual = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果是否相等：" + isEqual);
    }

    public static int[] sortArray(int[] nums) {
        if (nums.length > 1) {
            quickSort2(nums, 0, nums.length - 1);
        }
        return nums;
    }

    // 【不推荐】随机快排，经典解法
    public static void quickSort1(int[] arr, int l, int r) {
        if (l >= r) {
            return;
        }
        // 随机取数，在概率上把快速排序的时间复杂度收敛到O(N * logN)
        int x = arr[l + (int) (Math.random() * (r - l + 1))];
        int mid = partition1(arr, l, r, x);
        quickSort1(arr, l, mid - 1);
        quickSort1(arr, mid + 1, r);
    }

    private static int partition1(int[] arr, int left, int right, int x) {
        // <=x 区域的右边界位置
        int index = left;
        // 元素x的位置
        int xi = 0;
        for (int i = left; i <= right; i++) {
            // 如果当前元素 <= x，将其放入 <=x 的区域
            if (arr[i] <= x) {
                // 交换当前元素与 <=x 区域的右边界元素
                swap(arr, i, index);
                if (arr[index] == x) {
                    xi = index;
                }
                // 扩展 <=x 区域的右边界
                index++;
            }
        }

        // 将 xi 位置的 x 交换到 <=x 区域的最后一个位置（a-1）
        swap(arr, xi, index - 1);

        return index - 1;
    }

    public static void swap(int[] arr, int i, int j) {
        int tmp = arr[i];
        arr[i] = arr[j];
        arr[j] = tmp;
    }

    /**
     * 荷兰国旗问题划分
     * 初始值 left = -1，right = arr.length
     * 1、arr[i] == num，i++
     * 2、arr[i] < num，arr[i] 与 小于 num 的区域右边第一个元素交换，然后 i++
     * 3、arr[i] > num，arr[i] 与 大于 num 的区域左边第一个元素交换，i 不变
     *
     * @param arr   数组
     * @param pivot 划分值
     */
    public static int[] dutchNationalFlag(int[] arr, int l, int r, int pivot) {
        if (arr == null || arr.length < 2) {
            return new int[]{0, 1};
        }

        // 小于 pivot 区域的右边界
        int low = l;
        // 大于 pivot 区域的左边界
        int high = r;
        // 当前遍历的指针
        int i = l;

        // 遍历数组
        while (i <= high) {
            if (arr[i] < pivot) {
                // 如果当前元素小于 pivot，将其放入小于区域
                swap(arr, i, low);
                low++;
                i++;
            } else if (arr[i] > pivot) {
                // 如果当前元素大于 pivot，将其放入大于区域
                swap(arr, i, high);
                high--;
                // 注意：这里不需要 i++，因为交换后的 arr[i] 还未检查
            } else {
                // 如果当前元素等于 pivot，直接跳过
                i++;
            }
        }

        return new int[]{low, high};
    }

    // 【推荐】随机快排，使用荷兰问题解法改进
    public static void quickSort2(int[] arr, int l, int r) {
        if (l >= r) {
            return;
        }
        // 随机取数，在概率上把快速排序的时间复杂度收敛到O(N * logN)
        int x = arr[l + (int) (Math.random() * (r - l + 1))];
        int[] pivots = partition2(arr, l, r, x);
        quickSort2(arr, l, pivots[0] - 1);
        quickSort2(arr, pivots[1] + 1, r);
    }

    private static int[] partition2(int[] arr, int left, int right, int x) {
        return dutchNationalFlag(arr, left, right, x);
    }

}
