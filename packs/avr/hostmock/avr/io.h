/*
 * Tiêu đề GIẢ cho máy chủ — Platform Pack `avr`.
 *
 * Vì sao tệp này tồn tại
 * ----------------------
 * Công đoạn C2 nói firmware được viết TÁCH LỚP TRỪU TƯỢNG PHẦN CỨNG chính là
 * để dịch và chạy được trên máy tính. Cổng `unittests` thực hiện lời hứa ấy:
 * nó dịch `src/<module>.c` bằng trình dịch của máy chủ rồi gọi qua `ctypes`.
 *
 * Mã chạm thanh ghi thì `#include <avr/io.h>`, và trên máy chủ tệp ấy không
 * tồn tại. `pack.yaml` khai `host_test.mock_include: hostmock` từ SL-134, và
 * thư mục ấy CHƯA BAO GIỜ ĐƯỢC TẠO — nên mọi module chạm thanh ghi đều chết ở
 * cổng thứ tư với `fatal error: 'avr/io.h' file not found`, và vòng tự sửa
 * đốt sạch ba lượt cho một thứ không bản vá nào của module sửa được (SL-143).
 *
 * Nó KHÔNG mô phỏng con chip
 * ---------------------------
 * Thanh ghi ở đây là các ô nhớ thường. Ghi vào `PORTB` chỉ đổi một byte trong
 * mảng; không có chân nào nhấc lên, không ngoại vi nào chạy. Bài kiểm trên máy
 * chủ vì thế kiểm được: thứ tự thao tác bit, mặt nạ đúng bit, máy trạng thái,
 * số học. Nó KHÔNG kiểm được: giá trị thật trên chân, thời gian, hành vi ngoại
 * vi. Những thứ ấy thuộc cổng mô phỏng và nghiệm thu vật lý tại G4.
 *
 * Bài kiểm dựng cảnh bằng cách ghi thẳng vào thanh ghi trước khi gọi hàm —
 * ví dụ đặt `PINB` rồi gọi hàm đọc nút.
 */
#ifndef EAA_HOSTMOCK_AVR_IO_H
#define EAA_HOSTMOCK_AVR_IO_H

#include <stdint.h>

/* Thanh ghi là BIẾN TOÀN CỤC mang đúng tên của nó.
 *
 * Không phải macro trỏ vào một mảng. Lý do rất thực tế: bài kiểm Python với
 * tới thanh ghi bằng `ctypes.c_uint8.in_dll(lib, "PORTB")` — đó là phản xạ
 * đầu tiên của bất cứ ai viết bài kiểm, và mô hình cũng làm đúng thế. Macro
 * thì không sinh ra ký hiệu nào để `dlsym` tìm thấy, nên bài kiểm chết với
 * `symbol not found` dù mã C hoàn toàn đúng (SL-145).
 *
 * Bên C chúng vẫn dùng y hệt: `PORTB |= (1 << PORTB2);`
 */
/* --- Cổng vào/ra ------------------------------------------------------- */
extern volatile uint8_t PINB;
extern volatile uint8_t DDRB;
extern volatile uint8_t PORTB;
extern volatile uint8_t PINC;
extern volatile uint8_t DDRC;
extern volatile uint8_t PORTC;
extern volatile uint8_t PIND;
extern volatile uint8_t DDRD;
extern volatile uint8_t PORTD;

/* --- Bộ đếm ------------------------------------------------------------ */
extern volatile uint8_t TCCR0A;
extern volatile uint8_t TCCR0B;
extern volatile uint8_t TCNT0;
extern volatile uint8_t OCR0A;
extern volatile uint8_t OCR0B;
extern volatile uint8_t TIMSK0;

extern volatile uint8_t TCCR1A;
extern volatile uint8_t TCCR1B;
extern volatile uint8_t TCCR1C;
extern volatile uint8_t TIMSK1;
/* Thanh ghi 16 bit của bộ đếm 1 — trên chip là cặp byte cao/thấp. */
extern volatile uint8_t TCNT1L;
extern volatile uint8_t TCNT1H;
extern volatile uint8_t OCR1AL;
extern volatile uint8_t OCR1AH;
extern volatile uint8_t OCR1BL;
extern volatile uint8_t OCR1BH;
extern volatile uint16_t TCNT1;
extern volatile uint16_t OCR1A;
extern volatile uint16_t OCR1B;

extern volatile uint8_t TCCR2A;
extern volatile uint8_t TCCR2B;
extern volatile uint8_t TCNT2;
extern volatile uint8_t OCR2A;
extern volatile uint8_t OCR2B;
extern volatile uint8_t TIMSK2;

/* --- Bus hai dây ------------------------------------------------------- */
extern volatile uint8_t TWBR;
extern volatile uint8_t TWSR;
extern volatile uint8_t TWAR;
extern volatile uint8_t TWDR;
extern volatile uint8_t TWCR;
extern volatile uint8_t TWAMR;

/* --- Cổng nối tiếp ----------------------------------------------------- */
extern volatile uint8_t UCSR0A;
extern volatile uint8_t UCSR0B;
extern volatile uint8_t UCSR0C;
extern volatile uint8_t UBRR0L;
extern volatile uint8_t UBRR0H;
extern volatile uint8_t UDR0;
extern volatile uint16_t UBRR0;

/* --- Điều khiển chung -------------------------------------------------- */
extern volatile uint8_t MCUCR;
extern volatile uint8_t SREG;

/* --- Vị trí bit -------------------------------------------------------- */
/* Đặt bằng số thứ tự bit, đúng như tài liệu. Mã thường viết `(1 << DDB4)`,
 * nên thiếu tên nào là lỗi dịch chứ không phải sai âm thầm. */
#define PINB0 0
#define PINB1 1
#define PINB2 2
#define PINB3 3
#define PINB4 4
#define PINB5 5
#define PINB6 6
#define PINB7 7
#define DDB0 0
#define DDB1 1
#define DDB2 2
#define DDB3 3
#define DDB4 4
#define DDB5 5
#define DDB6 6
#define DDB7 7
#define PORTB0 0
#define PORTB1 1
#define PORTB2 2
#define PORTB3 3
#define PORTB4 4
#define PORTB5 5
#define PORTB6 6
#define PORTB7 7

#define PIND0 0
#define PIND1 1
#define PIND2 2
#define PIND3 3
#define PIND4 4
#define PIND5 5
#define PIND6 6
#define PIND7 7
#define DDD0 0
#define DDD1 1
#define DDD2 2
#define DDD3 3
#define DDD4 4
#define DDD5 5
#define DDD6 6
#define DDD7 7
#define PORTD0 0
#define PORTD1 1
#define PORTD2 2
#define PORTD3 3
#define PORTD4 4
#define PORTD5 5
#define PORTD6 6
#define PORTD7 7

#define PINC0 0
#define PINC1 1
#define PINC2 2
#define PINC3 3
#define PINC4 4
#define PINC5 5
#define DDC0 0
#define DDC1 1
#define DDC2 2
#define DDC3 3
#define DDC4 4
#define DDC5 5
#define PORTC0 0
#define PORTC1 1
#define PORTC2 2
#define PORTC3 3
#define PORTC4 4
#define PORTC5 5

/* Bit của bộ đếm */
#define WGM00 0
#define WGM01 1
#define WGM02 3
#define CS00 0
#define CS01 1
#define CS02 2
#define OCIE0A 1
#define WGM10 0
#define WGM11 1
#define WGM12 3
#define WGM13 4
#define CS10 0
#define CS11 1
#define CS12 2
#define OCIE1A 1
#define OCIE1B 2
#define WGM20 0
#define WGM21 1
#define WGM22 3
#define CS20 0
#define CS21 1
#define CS22 2
#define OCIE2A 1
#define OCIE2B 2

/* Bit của bus hai dây */
#define TWINT 7
#define TWEA 6
#define TWSTA 5
#define TWSTO 4
#define TWWC 3
#define TWEN 2
#define TWIE 0
#define TWPS0 0
#define TWPS1 1

/* Bit của cổng nối tiếp */
#define RXC0 7
#define TXC0 6
#define UDRE0 5
#define FE0 4
#define DOR0 3
#define UPE0 2
#define U2X0 1
#define MPCM0 0
#define RXCIE0 7
#define TXCIE0 6
#define UDRIE0 5
#define RXEN0 4
#define TXEN0 3
#define UCSZ00 1
#define UCSZ01 2
#define UCSZ02 2
#define USBS0 3
#define UPM00 4
#define UPM01 5
#define UMSEL00 6
#define UMSEL01 7

/* Tên chân kiểu cũ của avr-libc: PB0..PB7, PC0..PC5, PD0..PD7.
 *
 * avr-libc định nghĩa chúng và mã thật hay dùng — `(1 << PD4)` đọc gọn hơn
 * `(1 << PORTD4)`. Mock thiếu chúng thì cổng dịch AVR ĐẠT còn cổng kiểm trên
 * máy chủ đỏ với `use of undeclared identifier 'PD4'`, và mô hình bị đẩy vào
 * vòng vá cho một lỗi của MOCK chứ không của mã (SL-145).
 *
 * Quy tắc: mock phải giống thật ở mọi tên mã sẽ dùng. Thiếu một tên là dựng
 * ra một lỗi không tồn tại trên thiết bị.
 */
#define PB0 0
#define PB1 1
#define PB2 2
#define PB3 3
#define PB4 4
#define PB5 5
#define PB6 6
#define PB7 7
#define PC0 0
#define PC1 1
#define PC2 2
#define PC3 3
#define PC4 4
#define PC5 5
#define PC6 6
#define PD0 0
#define PD1 1
#define PD2 2
#define PD3 3
#define PD4 4
#define PD5 5
#define PD6 6
#define PD7 7

/* Bit của MCUCR */
#define PUD 4

#endif /* EAA_HOSTMOCK_AVR_IO_H */
