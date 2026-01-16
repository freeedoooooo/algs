package alg.algs001;

import util.MyBitUtil;

/**
 * 异或运算（异或=无进位相加）
 * 题目1、一个数组，找出唯一的奇数个数字
 * 题目2、一个整型数，怎么提取最右侧的1
 * 题目3、一个数组中，有2组数出现了奇数次，其他数字都是偶数次，找到这两个数
 */
public class XOROperations {

    public static void main(String[] args) {
        int[] arr = {1, 1, 2, 2, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 8, 8, 8};
        findOddNumber2(arr);
    }

    public static int findOddNumber1(int[] arr) {
        int res = 0;
        for (int j : arr) {
            res ^= j;
        }
        return res;
    }

    /**
     * 找出两个数出现了奇数次的数
     */
    public static void findOddNumber2(int[] arr) {
        // 将这2个奇数个的数的异或结果看作一个整体
        int oddXOR = findOddNumber1(arr);
        System.out.println(MyBitUtil.toBinaryWithLeadingZeros(8, oddXOR));

        // 提取最右侧的1，举例：比如 10101000 ，那么 00001000 就是最右侧的1
        int rightOne = oddXOR & (~oddXOR + 1);
        System.out.println(MyBitUtil.toBinaryWithLeadingZeros(8, rightOne));

        int odd1 = 0;
        for (int j : arr) {
            if ((j & rightOne) != 0) {
                odd1 ^= j;
            }
        }
        System.out.println(odd1);

        int odd2 = oddXOR ^ odd1;
        System.out.println(odd2);
    }

}
