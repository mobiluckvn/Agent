/* Phần đo của kịch bản DS-05 — kiểm nguồn dưới tải.
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN. Bộ khung do Platform Pack cấp lo phần chung.
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);
 *     void eaa_emit(const char *);
 *
 * Mẹo đo Vcc mà không cần thêm linh kiện nào
 * -------------------------------------------
 * ADC của chip đo được điện áp tham chiếu nội 1,1 V khi lấy chính Vcc làm
 * thang. Đảo ngược tỉ số ấy thì ra Vcc: Vcc = 1,1 × 1024 / số_đọc. Nhờ vậy
 * phép kiểm brown-out chạy được trên bo trần, không cần cầu chia áp và không
 * chiếm thêm chân nào.
 *
 * Vì sao đo cùng lúc với động cơ chạy: sụt áp khi tăng tốc là nguyên nhân
 * reset ngẫu nhiên đã được lường trước ở công đoạn B2, và nó CHỈ xuất hiện
 * dưới tải. Đo lúc robot nằm yên sẽ cho ra một con số đẹp và vô nghĩa.
 *
 * Kịch bản này có mục `manual` trong diagnostics.yaml: dòng tiêu thụ và nhiệt
 * độ driver không con chip nào tự đo được về chính nó, nên chúng đi qua kênh
 * thứ ba — người cầm dụng cụ (N-084).
 */

#include <stdint.h>
#include <avr/io.h>
#include <util/delay.h>

void eaa_emit(const char *json);

#define PIN_EN     PB0
#define PIN_STEP_L PB1
#define PIN_STEP_R PB3

/* Điện áp tham chiếu nội, đơn vị milivôn. Giá trị danh định; sai số thực tế
 * ±10% theo tài liệu, nên con số Vcc suy ra từ đây là ƯỚC LƯỢNG chứ không
 * phải phép đo chuẩn — mục `manual` bằng đồng hồ mới là phép đo chuẩn. */
#define VREF_MV        1100UL
#define DIAG_CYCLES    200u    /* 200 lượt × ~10 ms ≈ 2 giây dưới tải */
#define DIAG_HALF_US   500u

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

static void adc_init(void)
{
    /* Thang = Vcc (REFS0), đầu vào = tham chiếu nội 1,1 V (MUX3..0 = 1110). */
    ADMUX = (uint8_t)((1u << REFS0) | (1u << MUX3) | (1u << MUX2) | (1u << MUX1));
    /* Chia tần 128 → 125 kHz ở 16 MHz, trong dải 50–200 kHz mà ADC cần để đủ
     * số bit. Chạy nhanh hơn thì vẫn ra số, chỉ là số kém chính xác. */
    ADCSRA = (uint8_t)((1u << ADEN) | (1u << ADPS2) | (1u << ADPS1) | (1u << ADPS0));
    /* Tham chiếu nội cần thời gian ổn định sau khi chọn. */
    _delay_ms(2);
}

static uint16_t adc_doc(void)
{
    uint16_t han = 0u;
    ADCSRA |= (uint8_t)(1u << ADSC);
    while (ADCSRA & (1u << ADSC)) {
        if (++han == 0u) {
            return 0u;   /* quá hạn — trả 0, và 0 sẽ lộ ra ở phép chia dưới */
        }
    }
    return ADC;
}

static uint16_t vcc_mv(void)
{
    uint16_t doc = adc_doc();
    if (doc == 0u) {
        return 0u;
    }
    return (uint16_t)((VREF_MV * 1024UL) / (uint32_t)doc);
}

void diag_run(void)
{
    char khung[96];
    uint8_t i = 0u;
    const char *k;
    uint16_t nho_nhat = 0xFFFFu;
    uint16_t luc_nghi;

    DDRB |= (uint8_t)((1u << PIN_EN) | (1u << PIN_STEP_L) | (1u << PIN_STEP_R));
    PORTB |= (uint8_t)(1u << PIN_EN);      /* driver tắt */
    adc_init();

    /* Mốc lúc nghỉ, để phần phân tích biết sụt BAO NHIÊU chứ không chỉ biết
     * giá trị thấp nhất là bao nhiêu. Một bo cấp 4,6 V lúc nghỉ và một bo cấp
     * 5,0 V rồi sụt xuống 4,6 V là hai tình trạng khác hẳn nhau. */
    luc_nghi = vcc_mv();

    PORTB &= (uint8_t)~(1u << PIN_EN);     /* bật driver */
    _delay_ms(10);

    for (uint16_t c = 0u; c < DIAG_CYCLES; c++) {
        /* Phát mười xung cho mỗi động cơ rồi đo — đo GIỮA lúc đang tải, không
         * đo sau khi đã ngừng. */
        for (uint8_t x = 0u; x < 10u; x++) {
            PORTB |= (uint8_t)((1u << PIN_STEP_L) | (1u << PIN_STEP_R));
            _delay_us(DIAG_HALF_US);
            PORTB &= (uint8_t)~((1u << PIN_STEP_L) | (1u << PIN_STEP_R));
            _delay_us(DIAG_HALF_US);
        }
        uint16_t v = vcc_mv();
        if (v != 0u && v < nho_nhat) {
            nho_nhat = v;
        }
    }

    PORTB |= (uint8_t)(1u << PIN_EN);      /* tắt lại khi xong */

    if (nho_nhat == 0xFFFFu) {
        eaa_emit("{\"vcc_min_v\": null, \"error\": \"ADC khong tra ve so\"}");
        return;
    }

    k = "{\"vcc_idle_v\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(luc_nghi / 1000u, &khung[i]);
    khung[i++] = '.';
    i += so_ra_chu((luc_nghi / 100u) % 10u, &khung[i]);
    i += so_ra_chu((luc_nghi / 10u) % 10u, &khung[i]);
    k = ", \"vcc_min_v\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(nho_nhat / 1000u, &khung[i]);
    khung[i++] = '.';
    i += so_ra_chu((nho_nhat / 100u) % 10u, &khung[i]);
    i += so_ra_chu((nho_nhat / 10u) % 10u, &khung[i]);
    /* Bộ đếm reset đọc từ cờ nguồn của chip: bit BORF cho biết lần khởi động
     * gần nhất là do sụt áp. Đây là bằng chứng TRỰC TIẾP cho brown-out, đáng
     * hơn hẳn việc suy từ con số điện áp. */
    k = ", \"resets\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu((MCUSR & (1u << BORF)) ? 1u : 0u, &khung[i]);
    khung[i++] = '}';
    khung[i] = '\0';

    eaa_emit(khung);
}
