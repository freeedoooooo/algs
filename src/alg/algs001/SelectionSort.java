package alg.algs001;

import util.MyArrayUtil;

/**
 * 选择排序
 */
public class SelectionSort {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArray(8000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        selectionSort(arr1);
        boolean sorted1 = MyArrayUtil.isSorted(arr1);
        System.out.println("方法1排序结果为：" + sorted1);

        mySelectionSort(arr2);
        boolean sorted2 = MyArrayUtil.isSorted(arr2);
        System.out.println("方法2排序结果为：" + sorted2);

        boolean isEqual = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果是否相等：" + isEqual);
    }

    /**
     * 使用选择排序算法对整数数组进行排序
     * 选择排序的工作原理是遍历数组，每次找到剩余未排序部分的最小元素，并将其放到正确的位置
     * 这个方法直接修改输入的数组，不需要额外的存储空间
     *
     * @param array 待排序的整数数组
     */
    public static void selectionSort(int[] array) {
        // 遍历数组，每次迭代选择剩余未排序部分的最小元素
        for (int i = 0; i < array.length - 1; i++) {
            // 假设当前位置的元素是最小的
            int minIndex = i;
            // 继续遍历剩余未排序的部分
            for (int j = i + 1; j < array.length; j++) {
                // 如果找到更小的元素，则更新最小元素的索引
                if (array[j] < array[minIndex]) {
                    minIndex = j;
                }
            }
            // 如果找到的最小元素不在当前位置，则将其与当前位置的元素交换
            if (minIndex != i) {
                MyArrayUtil.swap(array, i, minIndex);
            }
        }
    }


    public static void mySelectionSort(int[] array) {
        if (array == null || array.length <= 1) {
            return;
        }
        for (int i = 0; i < array.length - 1; i++) {
            int minIndex = i;
            for (int j = minIndex; j < array.length; j++) {
                if (array[j] < array[minIndex]) {
                    minIndex = j;
                }
            }
            MyArrayUtil.swap(array, i, minIndex);
        }
    }

}
