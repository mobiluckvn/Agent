/* Phần đo của kịch bản DS-06 — đặc tính thời gian thực (N-083).
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN. Bộ khung do Platform Pack cấp lo phần chung.
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);
 *     void eaa_emit(const char *);
 *
 * Bốn số, và số thứ tư là số hay bị bỏ nhất
 * ------------------------------------------
 *   isr_period_ms      chu kỳ ngắt trung bình
 *   jitter_us          dao động chu kỳ — độ lệch lớn nhất so với danh định
 *   isr_period_max_ms  chu kỳ DÀI NHẤT quan sát được
 *   cpu_load_pct       phần thời gian CPU bận trong vòng lặp điều khiển
 *
 * Trung bình gần như luôn đẹp. Một vòng điều khiển 10 ms trung bình vẫn có thể
 * có một chu kỳ 23 ms mỗi vài giây — và với con lắc ngược thì chính chu kỳ ấy
 * quyết định robot đứng hay ngã, chứ không phải trung bình. Nên kịch bản này
 * báo cả TRƯỜNG HỢP XẤU NHẤT, và ràng buộc `control_loop_ms` được đối chiếu
 * với nó chứ không với trung bình.
 *
 * Cách đo: Timer1 chạy CTC sinh ngắt mỗi 10 ms; Timer0 chạy tự do làm thước
 * đo phụ. Dùng HAI bộ đếm độc lập có chủ ý — một bộ đếm tự đo chính mình thì
 * mọi sai số nguồn xung nhịp đều triệt tiêu và ta luôn được một con số hoàn
 * hảo, hoàn hảo vì nó không đo gì cả.
 */

#include <stdint.h>
#include <avr/io.h>
#include <avr/interrupt.h>

void eaa_emit(const char *json);

/* Danh định 10 ms, khớp ràng buộc control_loop_ms của dự án. */
#define DIAG_PERIOD_MS   10u
#define DIAG_SAMPLES     200u   /* 200 × 10 ms = 2 giây quan sát */

/* Timer0 chia tần 64 → mỗi nhịp 4 µs ở 16 MHz. Timer0 tràn sau 256 nhịp
 * (1024 µs), nên nó đo được khoảng cách tới ~1 ms mỗi lần tràn; ta đếm số lần
 * tràn để với tới thang 10 ms. */
#define T0_TICK_US       4u
#define T0_WRAP_US       1024u

static volatile uint16_t g_tran_t0 = 0u;
static volatile uint8_t  g_ngat = 0u;
static volatile uint16_t g_ban_ticks = 0u;

ISR(TIMER0_OVF_vect)
{
    g_tran_t0++;
}

ISR(TIMER1_COMPA_vect)
{
    /* Ngắt này cố ý làm rất ít việc: nó chỉ dựng một cờ. Đo thời gian TỪ TRONG
     * ngắt sẽ tính cả thời gian của chính phép đo, và với ngắt 10 ms thì phần
     * ấy không nhỏ so với thứ đang đo. */
    g_ngat = 1u;
}

static uint8_t so_ra_chu(uint32_t gia_tri, char *ra)
{
    char tam[12];
    uint8_t n = 0u, i = 0u;
    do {
        tam[n++] = (char)('0' + (gia_tri % 10u));
        gia_tri /= 10u;
    } while (gia_tri != 0u);
    while (n != 0u) {
        ra[i++] = tam[--n];
    }
    return i;
}

/* Mốc thời gian hiện tại, đơn vị micro giây, đọc từ Timer0. */
static uint32_t moc_us(void)
{
    uint8_t sreg = SREG;
    cli();
    uint16_t tran = g_tran_t0;
    uint8_t dem = TCNT0;
    /* Đọc lại cờ tràn: nếu tràn xảy ra ĐÚNG giữa hai lệnh trên thì `tran` cũ
     * đi cùng `dem` mới, và kết quả lệch nguyên một vòng. */
    if ((TIFR0 & (1u << TOV0)) && dem < 128u) {
        tran++;
    }
    SREG = sreg;
    return (uint32_t)tran * T0_WRAP_US + (uint32_t)dem * T0_TICK_US;
}

static void timer_init(void)
{
    /* Timer0: tự do, chia 64, bật ngắt tràn — thước đo. */
    TCCR0A = 0u;
    TCCR0B = (uint8_t)((1u << CS01) | (1u << CS00));
    TIMSK0 = (uint8_t)(1u << TOIE0);

    /* Timer1: CTC, chia 64, so khớp mỗi 10 ms — vật được đo.
     * 16 MHz / 64 = 250 kHz → 2500 nhịp là 10 ms. */
    TCCR1A = 0u;
    TCCR1B = (uint8_t)((1u << WGM12) | (1u << CS11) | (1u << CS10));
    OCR1A = (uint16_t)((F_CPU / 64UL / 1000UL) * DIAG_PERIOD_MS - 1UL);
    TIMSK1 = (uint8_t)(1u << OCIE1A);
}

/* Việc giả lập tải của vòng điều khiển. Số vòng lặp chọn để tốn khoảng vài
 * trăm micro giây — cùng bậc với một vòng PID số nguyên trên lõi 8 bit. */
static void viec_gia(void)
{
    volatile int32_t acc = 0;
    for (uint16_t i = 0u; i < 400u; i++) {
        acc += (int32_t)i * 3;
    }
    (void)acc;
}

void diag_run(void)
{
    char khung[128];
    uint8_t i = 0u;
    const char *k;

    uint32_t truoc;
    uint32_t tong_chu_ky = 0u;
    uint32_t tong_ban = 0u;
    uint32_t dai_nhat = 0u;
    uint32_t ngan_nhat = 0xFFFFFFFFUL;
    uint16_t thu = 0u;

    timer_init();
    sei();

    /* Bỏ lượt đầu: nó tính cả thời gian từ lúc bật bộ đếm tới ngắt đầu tiên,
     * một khoảng chẳng liên quan gì tới chu kỳ. */
    while (!g_ngat) { }
    g_ngat = 0u;
    truoc = moc_us();

    while (thu < DIAG_SAMPLES) {
        while (!g_ngat) { }
        g_ngat = 0u;

        uint32_t bay_gio = moc_us();
        uint32_t chu_ky = bay_gio - truoc;
        truoc = bay_gio;

        /* Đo phần CPU bận: chạy việc giả rồi lấy hiệu hai mốc. */
        uint32_t bat_dau_ban = moc_us();
        viec_gia();
        uint32_t ban = moc_us() - bat_dau_ban;

        tong_chu_ky += chu_ky;
        tong_ban += ban;
        if (chu_ky > dai_nhat) { dai_nhat = chu_ky; }
        if (chu_ky < ngan_nhat) { ngan_nhat = chu_ky; }
        thu++;
    }

    cli();

    {
        uint32_t tb_us = tong_chu_ky / thu;
        uint32_t danh_dinh_us = (uint32_t)DIAG_PERIOD_MS * 1000UL;
        /* Dao động lấy theo biên độ đỉnh–đỉnh so với danh định, lấy phía lệch
         * nhiều hơn. Báo độ lệch chuẩn ở đây sẽ đẹp hơn và ít nói hơn. */
        uint32_t lech_tren = dai_nhat > danh_dinh_us ? dai_nhat - danh_dinh_us : 0u;
        uint32_t lech_duoi = ngan_nhat < danh_dinh_us ? danh_dinh_us - ngan_nhat : 0u;
        uint32_t jitter = lech_tren > lech_duoi ? lech_tren : lech_duoi;
        uint32_t tai = (tong_ban * 100u) / tong_chu_ky;

        k = "{\"isr_period_ms\": ";
        while (*k != '\0') { khung[i++] = *k++; }
        i += so_ra_chu(tb_us / 1000u, &khung[i]);
        khung[i++] = '.';
        i += so_ra_chu((tb_us / 100u) % 10u, &khung[i]);
        i += so_ra_chu((tb_us / 10u) % 10u, &khung[i]);

        k = ", \"isr_period_max_ms\": ";
        while (*k != '\0') { khung[i++] = *k++; }
        i += so_ra_chu(dai_nhat / 1000u, &khung[i]);
        khung[i++] = '.';
        i += so_ra_chu((dai_nhat / 100u) % 10u, &khung[i]);
        i += so_ra_chu((dai_nhat / 10u) % 10u, &khung[i]);

        k = ", \"jitter_us\": ";
        while (*k != '\0') { khung[i++] = *k++; }
        i += so_ra_chu(jitter, &khung[i]);

        k = ", \"cpu_load_pct\": ";
        while (*k != '\0') { khung[i++] = *k++; }
        i += so_ra_chu(tai, &khung[i]);

        k = ", \"samples\": ";
        while (*k != '\0') { khung[i++] = *k++; }
        i += so_ra_chu(thu, &khung[i]);

        khung[i++] = '}';
        khung[i] = '\0';
    }

    eaa_emit(khung);
}
