package practice.algs01_sort;

import java.util.PriorityQueue;

// 堆结构和堆排序
// 测试链接 : https://leetcode.cn/problems/sort-an-array/
public class HeapSort {

    public static int[] sortArray(int[] nums) {
        if (nums.length > 1) {
            // heapSort1为从顶到底建堆然后排序
            // heapSort2为从底到顶建堆然后排序
            // 用哪个都可以
            // heapSort1(nums);
            heapSort2(nums);
        }
        return nums;
    }

    // i位置的数，向上调整大根堆
    // arr[i] = x，x是新来的！往上看，直到不比父亲大，或者来到0位置(顶)
    public static void heapInsert(int[] arr, int i) {
        while (arr[i] > arr[(i - 1) / 2]) {
            swap(arr, i, (i - 1) / 2);
            i = (i - 1) / 2;
        }
    }

    // i位置的数，变小了，又想维持大根堆结构
    // 向下调整大根堆
    // 当前堆的大小为size
    public static void heapify(int[] arr, int i, int size) {
        // 左孩子下标
        int l = i * 2 + 1;
        while (l < size) {
            // 右孩子下标，l+1
            int r = l + 1;
            // 评选，最强的孩子，是哪个下标的孩子
            int best = r < size && arr[r] > arr[l] ? r : l;
            // 上面已经评选了最强的孩子，接下来，当前的数和最强的孩子之前，最强下标是谁
            best = arr[best] > arr[i] ? best : i;
            // 当前下标就是最大的，则直接停止；否则，交换
            if (best == i) {
                break;
            }
            swap(arr, best, i);
            // 继续向下调整大根堆
            i = best;
            l = i * 2 + 1;
        }
    }

    public static void swap(int[] arr, int i, int j) {
        int tmp = arr[i];
        arr[i] = arr[j];
        arr[j] = tmp;
    }

    // 从顶到底建立大根堆，O(n * logN)
    // 依次弹出堆内最大值并排好序，O(n * logN)
    // 整体时间复杂度O(n * logN)
    public static void heapSort1(int[] arr) {
        int n = arr.length;
        for (int i = 0; i < n; i++) {
            heapInsert(arr, i);
        }
        int size = n;
        while (size > 1) {
            size = size - 1;
            swap(arr, 0, size);
            heapify(arr, 0, size);
        }
    }

    // 从底到顶建立大根堆，O(n)
    // 依次弹出堆内最大值并排好序，O(n * logN)
    // 整体时间复杂度O(n * logN)
    public static void heapSort2(int[] arr) {
        int n = arr.length;
        for (int i = n - 1; i >= 0; i--) {
            heapify(arr, i, n);
        }
        int size = n;
        while (size > 1) {
            size = size - 1;
            swap(arr, 0, size);
            heapify(arr, 0, size);
        }
    }

    // 补充问题
    public void sortArrDistanceLessK(int[] arr, int k) {
        // 定义一个小根堆
        PriorityQueue<Integer> heap = new PriorityQueue<>();
        // 将 0 ~ k 放入堆中
        int index = 0;
        for (; index <= Math.min(k, arr.length - 1); index++) {
            heap.add(arr[index]);
        }
        int i = 0;
        for (; index < arr.length; i++, index++) {
            // 将当前值放入堆中
            heap.add(arr[index]);
            // 弹出最小值
            arr[i] = heap.poll();
        }
        // 弹出堆中剩余的值
        while (!heap.isEmpty()) {
            arr[i++] = heap.poll();
        }
    }

}
