package practice.algs01_sort;

/**
 * 归并排序
 * 1、递归实现，【！！！注意】执行顺序相当于二叉树的【后序遍历】
 * 2、迭代实现
 */
public class MergeSort {

    public static int MAX_SIZE = 10000;
    public static int[] temp = new int[MAX_SIZE];

    public static void main(String[] args) {

    }

    /**
     * 递归实现
     */
    public static void mergeSortRecursive(int[] arr) {
        if (arr == null || arr.length <= 1) {
            return;
        }
        sortRecursive(arr, 0, arr.length - 1);
    }

    private static void sortRecursive(int[] arr, int l, int r) {
        if (l == r) {
            return;
        }
        int m = l + (r - l) / 2;
        sortRecursive(arr, l, m);
        sortRecursive(arr, m + 1, r);
        merge(arr, l, m, r);
    }

    public static void merge(int[] arr, int l, int m, int r) {
        int i = l;
        int j = m + 1;
        int k = l;
        while (i <= m && j <= r) {
            if (arr[i] < arr[j]) {
                temp[k++] = arr[i++];
            } else {
                temp[k++] = arr[j++];
            }
        }
        while (i <= m) {
            temp[k++] = arr[i++];
        }
        while (j <= r) {
            temp[k++] = arr[j++];
        }
        for (int p = l; p <= r; p++) {
            arr[p] = temp[p];
        }
    }

    /**
     * 迭代实现
     */
    public static void mergeSortIterative(int[] arr) {
        if (arr == null || arr.length <= 1) {
            return;
        }
        int n = arr.length;
        // step 表示当前归并的子数组长度，初始为 1，每次翻倍
        for (int step = 1; step < n; step *= 2) {
            // 遍历数组，每次处理两个长度为 step 的子数组
            for (int left = 0; left < n; left += 2 * step) {
                // 第一个子数组的右边界
                int mid = left + step - 1;
                if (mid >= n - 1) {
                    // 如果第一个子数组的右边界已经超出数组范围，结束循环
                    break;
                }
                // 第二个子数组的右边界
                int right = Math.min(left + 2 * step - 1, n - 1);
                // 合并两个子数组
                merge(arr, left, mid, right);
            }
        }
    }

}
