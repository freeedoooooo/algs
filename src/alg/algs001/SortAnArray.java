package alg.algs001;

import util.MyArrayUtil;

// 归并排序 & 随机快排
// 测试链接 : https://leetcode.cn/problems/sort-an-array/
public class SortAnArray {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArray(5000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        MergeSort.mergeSortIterative(arr1);

    }

}
