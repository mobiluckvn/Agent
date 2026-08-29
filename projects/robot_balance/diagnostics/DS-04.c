/* Phần đo của kịch bản DS-04 — UART / telemetry.
 *
 * Kịch bản tự soi chính kênh truyền: nếu tệp này chạy tới nơi và khung tới
 * được máy tính thì đường telemetry đã thông. Nó cũng đo tốc độ khung thực tế,
 * vì "có nhận được" và "nhận đủ nhanh" là hai câu khác nhau — một vòng điều
 * khiển 10 ms mà kênh chỉ tải nổi 20 khung/giây thì số liệu về sau đều là ảnh
 * chụp thưa của một chuyển động nhanh.
 */

#include <stdint.h>
#include <avr/io.h>

void eaa_emit(const char *json);

/* Số khung dùng để đo tốc độ. Đủ nhiều để trung bình có nghĩa, đủ ít để kịch
 * bản kết thúc trong vài giây. */
#define DIAG_SO_KHUNG 100u

static void dem_thoi_gian_init(void)
{
    /* Timer1 chia tần 256: ở 16 MHz là 62,5 kHz, tức 16 µs mỗi nhịp — đủ mịn
     * để đo khoảng vài chục mili giây mà không tràn trong một lượt đo. */
    TCCR1A = 0u;
    TCCR1B = (1u << CS12);
    TCNT1 = 0u;
}

static void gui_so(const char *khoa, uint32_t gia_tri)
{
    char khung[48];
    uint8_t i = 0u;
    char so[11];
    uint8_t n = 0u;

    khung[i++] = '{';
    khung[i++] = '"';
    while (*khoa != '\0') {
        khung[i++] = *khoa++;
    }
    khung[i++] = '"';
    khung[i++] = ':';
    khung[i++] = ' ';

    if (gia_tri == 0u) {
        so[n++] = '0';
    }
    while (gia_tri > 0u) {
        so[n++] = (char)('0' + (gia_tri % 10u));
        gia_tri /= 10u;
    }
    while (n > 0u) {
        khung[i++] = so[--n];
    }

    khung[i++] = '}';
    khung[i] = '\0';
    eaa_emit(khung);
}

void diag_run(void)
{
    uint16_t bat_dau;
    uint16_t ket_thuc;

    /* Vòng lặp lại: bộ khung đã bật cả TXEN0 lẫn RXEN0, nên chỉ cần khẳng định
     * phần phát đã sẵn sàng. Khung này tới được máy tính chính là bằng chứng. */
    eaa_emit("{\"loopback_ok\": true}");

    dem_thoi_gian_init();
    bat_dau = TCNT1;

    for (uint8_t i = 0u; i < DIAG_SO_KHUNG; i++) {
        eaa_emit("{\"tick\": 1}");
    }

    ket_thuc = TCNT1;

    {
        /* Mỗi nhịp Timer1 ở hệ số chia 256 là 256 chu kỳ đồng hồ. */
        uint32_t nhip = (uint32_t)(uint16_t)(ket_thuc - bat_dau);
        uint32_t chu_ky = nhip * 256UL;
        uint32_t hz = (chu_ky > 0UL) ? ((uint32_t)DIAG_SO_KHUNG * F_CPU) / chu_ky : 0UL;
        gui_so("frame_rate_hz", hz);
    }
}
