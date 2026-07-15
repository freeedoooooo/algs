package util;

public class MyBitUtil {

    /**
     * 打印整数的二进制表示，并补齐前导零
     *
     * @param num 整数
     */
    public static String toBinaryWithLeadingZeros(int len, int num) {
        String binaryString = Integer.toBinaryString(num);
        return String.format("%" + len + "s", binaryString).replace(' ', '0');
    }

    /**
     * 打印整数的二进制表示，并补齐前导零
     *
     * @param num 整数
     */
    public static String toBinaryWithLeadingZeros(int num) {
        int len = 32;
        return toBinaryWithLeadingZeros(32, num);
    }

}
