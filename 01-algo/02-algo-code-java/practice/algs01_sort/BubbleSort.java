package practice.algs01_sort;

import util.MyArrayUtil;

/**
 * 冒泡排序
 */
public class BubbleSort {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArrayWithNegatives(8000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        SelectionSort.selectionSort(arr1);
        boolean sorted1 = MyArrayUtil.isSorted(arr1);
        System.out.println("方法1排序结果为：" + sorted1);

        bubbleSort(arr2);
        boolean sorted2 = MyArrayUtil.isSorted(arr2);
        System.out.println("方法2排序结果为：" + sorted2);

        boolean isEqual = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果是否相等：" + isEqual);
    }


    public static void bubbleSort(int[] nums) {
        if (nums == null || nums.length < 2) {
            return;
        }
        int end = nums.length - 1;
        while (end > 0) {
            for (int i = 0; i < end; i++) {
                if (nums[i] > nums[i + 1]) {
                    MyArrayUtil.swap(nums, i, i + 1);
                }
            }
            end--;
        }
    }

}
