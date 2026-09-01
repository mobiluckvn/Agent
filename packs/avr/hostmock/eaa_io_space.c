/*
 * Chỗ ở thật của các thanh ghi giả — Platform Pack `avr`.
 *
 * Tách khỏi tiêu đề vì mỗi bài kiểm dịch NHIỀU tệp `.c` vào cùng một thư viện
 * dùng chung. Một bản duy nhất ở đây nghĩa là mọi module trong cùng bài kiểm
 * nhìn thấy CÙNG các thanh ghi — đúng như trên chip.
 *
 * Chúng là BIẾN TOÀN CỤC mang đúng tên thanh ghi, không phải ô trong một mảng.
 * Nhờ thế bài kiểm Python với tới được bằng đúng câu quen thuộc nhất:
 *
 *     PORTB = ctypes.c_uint8.in_dll(lib, "PORTB")
 *     PINB.value = 0xEF          # kéo PB4 xuống — giả cảnh nhấn nút
 *     lib.button_init()
 *     assert PORTB.value & (1 << 4)   # kéo lên nội đã bật
 *
 * Macro trỏ vào mảng thì không sinh ra ký hiệu nào cho `dlsym`, và bài kiểm
 * chết với `symbol not found` dù mã C hoàn toàn đúng (SL-145).
 */
#include <stdint.h>

/* --- Cổng vào/ra --- */
volatile uint8_t PINB, DDRB, PORTB;
volatile uint8_t PINC, DDRC, PORTC;
volatile uint8_t PIND, DDRD, PORTD;

/* --- Bộ đếm --- */
volatile uint8_t TCCR0A, TCCR0B, TCNT0, OCR0A, OCR0B, TIMSK0;
volatile uint8_t TCCR1A, TCCR1B, TCCR1C, TIMSK1;
volatile uint8_t TCNT1L, TCNT1H, OCR1AL, OCR1AH, OCR1BL, OCR1BH;
volatile uint16_t TCNT1, OCR1A, OCR1B;
volatile uint8_t TCCR2A, TCCR2B, TCNT2, OCR2A, OCR2B, TIMSK2;

/* --- Bus hai dây --- */
volatile uint8_t TWBR, TWSR, TWAR, TWDR, TWCR, TWAMR;

/* --- Cổng nối tiếp --- */
volatile uint8_t UCSR0A, UCSR0B, UCSR0C, UBRR0L, UBRR0H, UDR0;
volatile uint16_t UBRR0;

/* --- Điều khiển chung --- */
volatile uint8_t MCUCR, SREG;
