package leetcode.p912_sort_an_array;

import practice.algs001.MergeSort;
import practice.algs001.QuickSort;
import util.MyArrayUtil;

// 归并排序 & 随机快排
// 测试链接 : https://leetcode.cn/problems/sort-an-array/
public class SortAnArray {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArray(5000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);
        int[] arr3 = MyArrayUtil.copyArray(arr1);

        MergeSort.mergeSortRecursive(arr1);
        MergeSort.mergeSortIterative(arr2);
        QuickSort.quickSort2(arr3, 0, arr2.length - 1);

        boolean isEqual1 = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果1是否相等：" + isEqual1);

        boolean isEqual2 = MyArrayUtil.isEqual(arr1, arr3);
        System.out.println("结果2是否相等：" + isEqual2);
    }

}
