/*
 * Tiêu đề GIẢ cho máy chủ — ngắt. Xem `avr/io.h` cùng thư mục để biết vì sao
 * thư mục này tồn tại và nó KHÔNG mô phỏng cái gì.
 *
 * `ISR(vect)` trên máy chủ trở thành một HÀM THƯỜNG mang đúng tên véc-tơ. Nhờ
 * thế bài kiểm gọi được thân ngắt qua `ctypes` — ví dụ gọi 40 lần liên tiếp
 * rồi đếm xem chân STEP đã lên xuống bao nhiêu lần. Đây là cách duy nhất kiểm
 * được logic trong ngắt mà không cần con chip.
 *
 * `sei()` và `cli()` không làm gì: trên máy chủ không có cờ ngắt toàn cục để
 * bật tắt. Chúng có mặt để mã dịch được, không phải để mô phỏng.
 *
 * `ATOMIC_BLOCK` cũng vậy — nó thành một khối thường. Nghĩa là bài kiểm trên
 * máy chủ KHÔNG chứng minh được một truy cập nhiều byte là nguyên tử; điều đó
 * chỉ kiểm được trên thiết bị.
 */
#ifndef EAA_HOSTMOCK_AVR_INTERRUPT_H
#define EAA_HOSTMOCK_AVR_INTERRUPT_H

#define ISR(vect) void vect(void)
#define ISR_NOBLOCK
#define ISR_NAKED

#define sei() ((void)0)
#define cli() ((void)0)

/* Tên véc-tơ hay dùng — khai để mã tham chiếu tới chúng dịch được. */
#define TIMER0_COMPA_vect TIMER0_COMPA_vect_fn
#define TIMER1_COMPA_vect TIMER1_COMPA_vect_fn
#define TIMER1_COMPB_vect TIMER1_COMPB_vect_fn
#define TIMER2_COMPA_vect TIMER2_COMPA_vect_fn
#define TIMER2_COMPB_vect TIMER2_COMPB_vect_fn
#define USART_RX_vect     USART_RX_vect_fn
#define USART_UDRE_vect   USART_UDRE_vect_fn
#define TWI_vect          TWI_vect_fn

#endif /* EAA_HOSTMOCK_AVR_INTERRUPT_H */
