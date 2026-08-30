/* Phần đo của kịch bản DS-03 — kiểm động cơ bước, từng động cơ một.
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN: nó biết chân STEP nào, chân DIR nào, chân
 * ENABLE nào. Bộ khung do Platform Pack cấp lo phần chung.
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);
 *     void eaa_emit(const char *);
 *
 * Ranh giới của kịch bản này, và vì sao nó cần kênh người
 * -------------------------------------------------------
 * Firmware chỉ biết nó ĐÃ PHÁT bao nhiêu xung và ở tần số nào. Nó KHÔNG biết
 * trục có quay hay không — dây STEP đứt, driver chưa chỉnh dòng, hay cuộn dây
 * hở đều cho ra cùng một số liệu "đã phát đủ 200 xung ở 1 kHz".
 *
 * Đó chính là chỗ phép giao hai kênh của AIS §7.4 có giá trị nhất, và là lý do
 * kịch bản này bắt buộc có mục `human` trong diagnostics.yaml. Đừng thêm cách
 * "tự phát hiện trục quay" vào đây: không có cảm biến vị trí thì mọi cách như
 * thế đều là suy diễn, và một suy diễn ở đây sẽ che mất đúng câu hỏi cần hỏi.
 */

#include <stdint.h>
#include <avr/io.h>
#include <util/delay.h>

void eaa_emit(const char *json);

/* Chân theo pin_map trong hardware_profile.yaml. Đổi bo là đổi ở đó và ở đây;
 * engine không biết những hằng số này và không được biết. */
#define PIN_EN     PB0   /* MOTOR_EN — mức THẤP là bật, chung cho hai driver */
#define PIN_STEP_L PB1   /* STEP_L */
#define PIN_DIR_L  PB2   /* DIR_L  */
#define PIN_STEP_R PB3   /* STEP_R */
#define PIN_DIR_R  PB4   /* DIR_R  */

/* 200 xung ở 1 kHz = 0,2 giây, và với vi bước 1/16 thì đó là 1/16 vòng.
 * Chọn dưới một vòng có chủ ý: robot đang kê trên giá, nhưng một lệnh quay
 * nhiều vòng vẫn đủ để một sợi dây bị cuốn vào bánh. */
#define DIAG_PULSES     200u
#define DIAG_HALF_US    500u   /* nửa chu kỳ → 1 kHz */

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

static void chan_ra(uint8_t chan)
{
    DDRB |= (uint8_t)(1u << chan);
}

static void dat(uint8_t chan, uint8_t muc)
{
    if (muc) {
        PORTB |= (uint8_t)(1u << chan);
    } else {
        PORTB &= (uint8_t)~(1u << chan);
    }
}

/* Phát n xung lên một chân, trả về số xung đã phát.
 *
 * Đếm lại thay vì tin vào tham số vòng lặp: hàm này là NGUỒN của con số
 * `pulses_emitted` mà kênh máy đối chiếu, nên nó phải đếm thứ thật sự xảy ra.
 */
static uint16_t phat_xung(uint8_t chan_step, uint16_t so_xung)
{
    uint16_t da_phat = 0u;
    for (uint16_t i = 0u; i < so_xung; i++) {
        dat(chan_step, 1u);
        _delay_us(DIAG_HALF_US);
        dat(chan_step, 0u);
        _delay_us(DIAG_HALF_US);
        da_phat++;
    }
    return da_phat;
}

static void bao_cao(const char *ten_dong_co, uint16_t xung, uint16_t tan_so)
{
    char khung[80];
    uint8_t i = 0u;
    const char *k;

    k = "{\"motor\": \"";
    while (*k != '\0') { khung[i++] = *k++; }
    while (*ten_dong_co != '\0') { khung[i++] = *ten_dong_co++; }
    k = "\", \"pulses_emitted\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(xung, &khung[i]);
    k = ", \"pulse_freq_hz\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(tan_so, &khung[i]);
    khung[i++] = '}';
    khung[i] = '\0';

    eaa_emit(khung);
}

void diag_run(void)
{
    chan_ra(PIN_EN);
    chan_ra(PIN_STEP_L);
    chan_ra(PIN_DIR_L);
    chan_ra(PIN_STEP_R);
    chan_ra(PIN_DIR_R);

    /* Tắt trước đã. Trạng thái chân sau reset không xác định, và một driver
     * bật sẵn trong lúc ta đang dựng cấu hình là một cú giật không ai chờ. */
    dat(PIN_EN, 1u);
    dat(PIN_STEP_L, 0u);
    dat(PIN_STEP_R, 0u);
    dat(PIN_DIR_L, 0u);
    dat(PIN_DIR_R, 0u);
    _delay_ms(50);

    dat(PIN_EN, 0u);       /* mức thấp = bật */
    _delay_ms(10);

    /* Từng động cơ MỘT, không đồng thời: chạy cả hai cùng lúc thì một trục
     * không quay sẽ bị che bởi tiếng và rung của trục kia — và kênh người là
     * kênh duy nhất trả lời được câu ấy. */
    bao_cao("trai", phat_xung(PIN_STEP_L, DIAG_PULSES),
            (uint16_t)(1000000UL / (2UL * DIAG_HALF_US)));
    _delay_ms(300);
    bao_cao("phai", phat_xung(PIN_STEP_R, DIAG_PULSES),
            (uint16_t)(1000000UL / (2UL * DIAG_HALF_US)));

    /* Tắt lại khi xong. Để driver giữ dòng sau khi đo là cách làm nóng động cơ
     * và đốt pin trong lúc không ai nhìn. */
    dat(PIN_EN, 1u);
}
