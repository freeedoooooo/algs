package alg.algs001;

import util.MyArrayUtil;

/**
 * 插入排序
 */
public class InsertionSort {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArray(5000, 10000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        insertionSort(arr1);
        boolean sorted1 = MyArrayUtil.isSorted(arr1);
        System.out.println("方法1排序结果为：" + sorted1);

        myInsertionSort(arr2);
        boolean sorted2 = MyArrayUtil.isSorted(arr2);
        System.out.println("方法2排序结果为：" + sorted2);

        boolean isEqual = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果是否相等：" + isEqual);
    }

    /**
     * 使用插入排序算法对整数数组进行排序
     * 插入排序的原理是将数组分为已排序和未排序两部分，初始时已排序部分只包含数组的第一个元素
     * 然后逐一将未排序部分的元素插入到已排序部分的适当位置，直至所有元素都插入完毕
     * 此方法直接在输入数组上进行排序，不需要额外的存储空间
     *
     * @param arr 待排序的整数数组
     */
    private static void insertionSort(int[] arr) {
        // 如果数组为空或只有一个元素，则不需要排序，直接返回
        if (arr == null || arr.length <= 1) {
            return;
        }

        // 遍历数组，从第二个元素开始，逐一将每个元素插入到已排序部分的适当位置
        for (int i = 1; i < arr.length; i++) {
            // 当前要插入的元素
            int current = arr[i];
            // j用于在已排序部分找到当前元素的插入位置，初始设为当前元素的前一个位置
            int j = i - 1;

            // 将所有大于当前元素的已排序元素向后移动一位，为当前元素腾出插入位置
            while (j >= 0 && arr[j] > current) {
                arr[j + 1] = arr[j];
                j--;
            }

            // 将当前元素插入到已排序部分的正确位置
            arr[j + 1] = current;
        }
    }

    /**
     * 插入排序
     * 位置交换，好理解，但是性能较差
     */
    private static void myInsertionSort(int[] array) {
        // 如果数组为空或只有一个元素，则不需要排序，直接返回
        if (array == null || array.length <= 1) {
            return;
        }
        // 从第二个元素开始，遍历数组
        for (int i = 1; i < array.length; i++) {
            // 将当前元素与前面已排序的元素逐个比较
            for (int j = 0; j < i; j++) {
                // 如果当前元素小于前面的元素，则交换位置
                if (array[i] < array[j]) {
                    MyArrayUtil.swap(array, i, j);
                }
            }
        }
    }

}
