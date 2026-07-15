package util;

/**
 * 数组工具类
 */
public class MyArrayUtil {

    /**
     * 随机生成一个整数数组
     *
     * @param size  数组的size
     * @param range 数组值的大小范围为[1,range]
     * @return 整数数组
     */
    public static int[] generateRandomArray(int size, int range) {
        int[] arr = new int[size];
        for (int i = 0; i < size; i++) {
            arr[i] = (int) (Math.random() * range) + 1;
        }
        return arr;
    }

    /**
     * 随机生成一个整数数组，支持负数
     *
     * @param size  数组的 size
     * @param range 数组值的大小范围为 [-range, range]
     * @return 整数数组
     */
    public static int[] generateRandomArrayWithNegatives(int size, int range) {
        int[] arr = new int[size];
        for (int i = 0; i < size; i++) {
            arr[i] = (int) (Math.random() * (2 * range + 1)) - range;
        }
        return arr;
    }

    /**
     * 拷贝数组
     */
    public static int[] copyArray(int[] arr) {
        if (arr == null) {
            return null;
        }
        int[] res = new int[arr.length];
        System.arraycopy(arr, 0, res, 0, arr.length);
        return res;
    }

    /**
     * 验证数组相等
     */
    public static boolean isEqual(int[] arr1, int[] arr2) {
        if (arr1 == null && arr2 == null) {
            return true;
        }
        if (arr1 == null || arr2 == null) {
            return false;
        }
        if (arr1.length != arr2.length) {
            return false;
        }
        for (int i = 0; i < arr1.length; i++) {
            if (arr1[i] != arr2[i]) {
                return false;
            }
        }
        return true;
    }

    /**
     * 验证数组有序
     */
    public static boolean isSorted(int[] arr) {
        if (arr == null || arr.length < 2) {
            return true;
        }
        for (int i = 1; i < arr.length; i++) {
            if (arr[i] < arr[i - 1]) {
                return false;
            }
        }
        return true;
    }

    /**
     * 交换数组中i,j位置的元素
     */
    public static void swap(int[] arr, int i, int j) {
        int temp = arr[i];
        arr[i] = arr[j];
        arr[j] = temp;
    }

}
