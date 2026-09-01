/*
 * Chỗ ở thật của không gian I/O giả — Platform Pack `avr`.
 *
 * Tách khỏi tiêu đề vì mỗi bài kiểm dịch NHIỀU tệp `.c` vào cùng một thư viện
 * dùng chung, và một biến định nghĩa trong tiêu đề sẽ thành nhiều bản sao (hoặc
 * lỗi trùng ký hiệu). Một bản duy nhất ở đây nghĩa là mọi module trong cùng bài
 * kiểm nhìn thấy CÙNG các thanh ghi — đúng như trên chip.
 *
 * `eaa_io_space()` trả con trỏ ra ngoài để bài kiểm Python đọc/ghi thẳng bằng
 * `ctypes`: dựng mức chân trước khi gọi hàm, và soi byte thanh ghi sau khi gọi.
 */
#include <stdint.h>

#define EAA_IO_SIZE 256

volatile uint8_t eaa_io[EAA_IO_SIZE];

volatile uint8_t *eaa_io_space(void)
{
    return eaa_io;
}
