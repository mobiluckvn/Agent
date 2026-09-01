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

/* Không gian I/O giả. `ctypes` lấy được con trỏ tới nó qua `eaa_io_space()`,
 * nên bài kiểm đọc/ghi được đúng những byte mà mã đang thao tác. */
#define EAA_IO_SIZE 256
extern volatile uint8_t eaa_io[EAA_IO_SIZE];
volatile uint8_t *eaa_io_space(void);

#define _EAA_REG(addr) (eaa_io[(addr)])

/* --- Cổng vào/ra ------------------------------------------------------- */
#define PINB   _EAA_REG(0x03)
#define DDRB   _EAA_REG(0x04)
#define PORTB  _EAA_REG(0x05)
#define PINC   _EAA_REG(0x06)
#define DDRC   _EAA_REG(0x07)
#define PORTC  _EAA_REG(0x08)
#define PIND   _EAA_REG(0x09)
#define DDRD   _EAA_REG(0x0A)
#define PORTD  _EAA_REG(0x0B)

/* --- Bộ đếm ------------------------------------------------------------ */
#define TCCR0A _EAA_REG(0x44)
#define TCCR0B _EAA_REG(0x45)
#define TCNT0  _EAA_REG(0x46)
#define OCR0A  _EAA_REG(0x47)
#define OCR0B  _EAA_REG(0x48)
#define TIMSK0 _EAA_REG(0x6E)

#define TCCR1A _EAA_REG(0x80)
#define TCCR1B _EAA_REG(0x81)
#define TCCR1C _EAA_REG(0x82)
#define TIMSK1 _EAA_REG(0x6F)
/* Thanh ghi 16 bit của bộ đếm 1 — trên chip là cặp byte cao/thấp. */
#define TCNT1L _EAA_REG(0x84)
#define TCNT1H _EAA_REG(0x85)
#define OCR1AL _EAA_REG(0x88)
#define OCR1AH _EAA_REG(0x89)
#define OCR1BL _EAA_REG(0x8A)
#define OCR1BH _EAA_REG(0x8B)
#define TCNT1  (*(volatile uint16_t *)&eaa_io[0x84])
#define OCR1A  (*(volatile uint16_t *)&eaa_io[0x88])
#define OCR1B  (*(volatile uint16_t *)&eaa_io[0x8A])

#define TCCR2A _EAA_REG(0xB0)
#define TCCR2B _EAA_REG(0xB1)
#define TCNT2  _EAA_REG(0xB2)
#define OCR2A  _EAA_REG(0xB3)
#define OCR2B  _EAA_REG(0xB4)
#define TIMSK2 _EAA_REG(0x70)

/* --- Bus hai dây ------------------------------------------------------- */
#define TWBR   _EAA_REG(0xB8)
#define TWSR   _EAA_REG(0xB9)
#define TWAR   _EAA_REG(0xBA)
#define TWDR   _EAA_REG(0xBB)
#define TWCR   _EAA_REG(0xBC)
#define TWAMR  _EAA_REG(0xBD)

/* --- Cổng nối tiếp ----------------------------------------------------- */
#define UCSR0A _EAA_REG(0xC0)
#define UCSR0B _EAA_REG(0xC1)
#define UCSR0C _EAA_REG(0xC2)
#define UBRR0L _EAA_REG(0xC4)
#define UBRR0H _EAA_REG(0xC5)
#define UDR0   _EAA_REG(0xC6)
#define UBRR0  (*(volatile uint16_t *)&eaa_io[0xC4])

/* --- Điều khiển chung -------------------------------------------------- */
#define MCUCR  _EAA_REG(0x55)
#define SREG   _EAA_REG(0x5F)

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

/* Bit của MCUCR */
#define PUD 4

#endif /* EAA_HOSTMOCK_AVR_IO_H */
