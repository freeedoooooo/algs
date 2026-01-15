package alg.algs001;

import util.MyArrayUtil;

import java.util.ArrayList;
import java.util.List;

/**
 * 计数排序
 * 核心逻辑：
 * 1、排序的 稳定性（即相同元素的相对顺序不变，需要先将计数数组转换为前缀和数组）
 * 2、使用偏移量支持负数
 */
public class CountingSort {

    public static void main(String[] args) {
        int[] arr1 = MyArrayUtil.generateRandomArrayWithNegatives(8000, 5000);
        int[] arr2 = MyArrayUtil.copyArray(arr1);

        SelectionSort.selectionSort(arr1);
        boolean sorted1 = MyArrayUtil.isSorted(arr1);
        System.out.println("方法1排序结果为：" + sorted1);

        countingSort(arr2);
        boolean sorted2 = MyArrayUtil.isSorted(arr2);
        System.out.println("方法2排序结果为：" + sorted2);

        boolean isEqual = MyArrayUtil.isEqual(arr1, arr2);
        System.out.println("结果是否相等：" + isEqual);
    }


    /**
     * 支持负数的计数排序方法
     *
     * @param arr 需要排序的数组
     */
    public static void countingSort(int[] arr) {
        if (arr == null || arr.length <= 1) {
            return;
        }

        // 找到数组中的最大值和最小值
        int max = arr[0];
        int min = arr[0];
        for (int num : arr) {
            if (num > max) {
                max = num;
            }
            if (num < min) {
                min = num;
            }
        }

        // 计算计数数组的大小
        int range = max - min + 1;
        int[] counter = new int[range];

        // 统计每个元素的出现次数
        for (int num : arr) {
            // 使用偏移量支持负数
            counter[num - min]++;
        }

        // 将计数数组转换为前缀和数组
        for (int i = 1; i < range; i++) {
            counter[i] += counter[i - 1];
        }

        // 创建临时数组，存储排序结果
        int[] output = new int[arr.length];
        // 【！！！注意，】从原数组的最后一个元素开始，向前遍历，这样做的目的是为了保证排序的 稳定性（即相同元素的相对顺序不变）。
        // 举例：参考本类中的方法 countingSortWithStudent
        for (int i = arr.length - 1; i >= 0; i--) {
            int num = arr[i];
            // 将元素放入正确位置
            // num - min：将当前元素 num 映射到计数数组 counter 的索引中（支持负数）。
            // counter[num - min]：表示当前元素 num 在排序后数组中的 最后一个位置（因为counter已转为【前缀和数组】，举例：如果有3个2，则是第3个2最终排序后是第几个数）。
            // counter[num - min] - 1：将位置转换为数组索引（因为数组索引从 0 开始）。
            output[counter[num - min] - 1] = num;
            // 更新计数
            counter[num - min]--;
        }

        // 将排序结果复制回原数组
        System.arraycopy(output, 0, arr, 0, arr.length);
    }


    private static void myCountingSort(int[] arr) {
        int[] counter = new int[6000];
        for (int value : arr) {
            counter[value]++;
        }
        int index = 0;
        for (int i = 0; i < counter.length; i++) {
            int num = counter[i];
            while (num > 0) {
                arr[index] = i;
                index++;
                num--;
            }
        }
    }

    public static void countingSortWithStudent(Student[] arr) {
        if (arr == null || arr.length <= 1) {
            return;
        }

        // 找到分数的最小值和最大值
        int min = arr[0].score;
        int max = arr[0].score;
        for (Student student : arr) {
            if (student.score < min) {
                min = student.score;
            }
            if (student.score > max) {
                max = student.score;
            }
        }

        // 创建对象列表数组
        List<Student>[] counter = new ArrayList[max - min + 1];
        for (int i = 0; i < counter.length; i++) {
            counter[i] = new ArrayList<>();
        }

        // 统计每个分数的学生
        for (Student student : arr) {
            counter[student.score - min].add(student);
        }

        // 将排序结果写回原数组
        int index = 0;
        for (List<Student> list : counter) {
            for (Student student : list) {
                arr[index++] = student;
            }
        }
    }

    public static class Student {
        String name;
        int score;

        Student(String name, int score) {
            this.name = name;
            this.score = score;
        }

        @Override
        public String toString() {
            return "{name: " + name + ", score: " + score + "}";
        }
    }

}
