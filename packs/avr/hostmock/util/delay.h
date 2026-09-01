/*
 * Tiêu đề GIẢ cho máy chủ — chờ bận.
 *
 * Ràng buộc của dự án CẤM `delay()`, và cổng phân tích tĩnh chặn nó. Tệp này
 * có mặt để mã DIAGNOSTIC (firmware chẩn đoán, không đi qua cổng static) dịch
 * được trên máy chủ, chứ không phải để mở đường cho mã sản phẩm dùng.
 *
 * Trên máy chủ chúng KHÔNG chờ. Một bài kiểm đo thời gian bằng hai hàm này sẽ
 * đo được số 0 — và đó là câu trả lời đúng: thời gian thật chỉ đo được trên
 * thiết bị.
 */
#ifndef EAA_HOSTMOCK_UTIL_DELAY_H
#define EAA_HOSTMOCK_UTIL_DELAY_H

#define _delay_ms(x) ((void)(x))
#define _delay_us(x) ((void)(x))

#endif /* EAA_HOSTMOCK_UTIL_DELAY_H */
