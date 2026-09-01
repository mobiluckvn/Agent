/* Phần đo của kịch bản DS-07 — HAI động cơ chạy TIẾN cùng lúc, liên tục.
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN: nó biết chân STEP nào, chân DIR nào, và mức
 * DIR nào là "tiến" cho từng bên. Bộ khung do Platform Pack cấp lo phần chung.
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);
 *     void eaa_emit(const char *);
 *
 * Vì sao cần kịch bản này bên cạnh DS-03
 * ---------------------------------------
 * DS-03 quay TỪNG động cơ một, mỗi cái 1/16 vòng (~22°). Đủ để trả lời "trục
 * có quay không" và "đúng chiều không", nhưng KHÔNG đủ để trả lời "quay có
 * trơn đều không": một cú giật 22° kết thúc trước khi tai kịp phân biệt tiếng
 * rít với tiếng khởi động bình thường.
 *
 * Kịch bản này cho cả hai chạy CÙNG LÚC và CÙNG CHIỀU TIẾN, đủ dài để nghe.
 * Nó trả lời thêm một câu nữa mà DS-03 không hỏi được: hai bánh có quay cùng
 * một chiều VẬT LÝ không.
 *
 * Câu ấy quan trọng vì hai động cơ lắp ĐỐI XỨNG GƯƠNG — cùng một mức DIR cho
 * ra hai chiều ngược nhau. `dir_forward_level` trong hardware_profile.yaml khai
 * mức nào là tiến cho từng bên; kịch bản này là phép kiểm của chính khai báo
 * ấy. Sai thì robot quay tại chỗ thay vì đi tới, và không cổng phần mềm nào
 * bắt được.
 *
 * Giới hạn có chủ ý
 * ------------------
 * Chạy CÓ HẠN, không phải "cho tới khi ai đó rút điện". Firmware này chạy
 * nhiều vòng nên nguy cơ cuốn dây vào bánh là thật — đó cũng là lý do
 * checklist an toàn của kịch bản có thêm một mục mà DS-03 không có.
 */

#include <stdint.h>
#include <avr/io.h>
#include <util/delay.h>

void eaa_emit(const char *json);

/* Chân theo pin_map trong hardware_profile.yaml; trái/phải chốt bằng quan sát
 * trên bo ngày 01/09/2026. Engine không biết những hằng số này và không được
 * biết. */
#define PIN_STEP_L PD7   /* STEP2 — D7, bánh TRÁI  */
#define PIN_DIR_L  PD6   /* DIR2  — D6            */
#define PIN_STEP_R PD5   /* STEP1 — D5, bánh PHẢI */
#define PIN_DIR_R  PD4   /* DIR1  — D4            */

/* Mức DIR để ROBOT đi TỚI, từ `dir_forward_level` của hồ sơ phần cứng.
 *
 * Hai bên KHÁC NHAU vì hai động cơ lắp đối xứng gương. Chiều TUYỆT ĐỐI chốt
 * bằng chính kịch bản này: bản trước dùng trái=0/phải=1 và người quan sát thấy
 * robot đi LÙI, nên hai giá trị đã đảo (SL-128). */
#define DIR_TIEN_L  1u
#define DIR_TIEN_R  0u

/* 4000 xung mỗi bánh ở 1 kHz = 4 giây, và với vi bước 1/16 trên động cơ 200
 * bước/vòng thì đó là 1,25 vòng.
 *
 * Đủ dài để nghe được tiếng rít và nhìn được độ đều; đủ ngắn để kịch bản kết
 * thúc trước khi người kịp rời mắt. Muốn dài hơn thì chạy lại nhiều lượt, chứ
 * đừng nâng số này: mỗi vòng thêm là thêm một cơ hội cho một sợi dây bị cuốn
 * vào bánh. */
#define DIAG_PULSES     4000u
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
    DDRD |= (uint8_t)(1u << chan);
}

static void dat(uint8_t chan, uint8_t muc)
{
    if (muc) {
        PORTD |= (uint8_t)(1u << chan);
    } else {
        PORTD &= (uint8_t)~(1u << chan);
    }
}

/* Phát xung lên CẢ HAI chân STEP cùng lúc, trả về số xung đã phát.
 *
 * Cùng lúc chứ không lần lượt: đây là điểm khác DS-03. Hai bánh chạy đồng thời
 * mới nghe được lệch nhịp giữa chúng, và mới thấy được robot có xu hướng lệch
 * về một bên hay không.
 *
 * Đếm lại thay vì tin vào tham số vòng lặp: hàm này là NGUỒN của con số
 * `pulses_emitted` mà kênh máy đối chiếu.
 */
static uint16_t phat_xung_hai_ben(uint16_t so_xung)
{
    uint16_t da_phat = 0u;
    for (uint16_t i = 0u; i < so_xung; i++) {
        dat(PIN_STEP_L, 1u);
        dat(PIN_STEP_R, 1u);
        _delay_us(DIAG_HALF_US);
        dat(PIN_STEP_L, 0u);
        dat(PIN_STEP_R, 0u);
        _delay_us(DIAG_HALF_US);
        da_phat++;
    }
    return da_phat;
}

static void bao_cao(uint16_t xung, uint16_t tan_so)
{
    char khung[96];
    uint8_t i = 0u;
    const char *k;

    k = "{\"pulses_emitted\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(xung, &khung[i]);
    k = ", \"pulse_freq_hz\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(tan_so, &khung[i]);
    k = ", \"dir_left\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(DIR_TIEN_L, &khung[i]);
    k = ", \"dir_right\": ";
    while (*k != '\0') { khung[i++] = *k++; }
    i += so_ra_chu(DIR_TIEN_R, &khung[i]);
    khung[i++] = '}';
    khung[i] = '\0';
    eaa_emit(khung);
}

void diag_run(void)
{
    chan_ra(PIN_STEP_L);
    chan_ra(PIN_DIR_L);
    chan_ra(PIN_STEP_R);
    chan_ra(PIN_DIR_R);

    /* Đưa hai chân STEP về mức thấp trước. Trạng thái chân sau reset không xác
     * định, và một xung rác trong lúc đang dựng cấu hình là một cú giật không
     * ai chờ. Không tắt được driver bằng phần mềm: bo không có nét ENABLE về
     * vi điều khiển. */
    dat(PIN_STEP_L, 0u);
    dat(PIN_STEP_R, 0u);

    /* Đặt chiều TIẾN cho từng bên, rồi chờ driver ổn định trước xung đầu. */
    dat(PIN_DIR_L, DIR_TIEN_L);
    dat(PIN_DIR_R, DIR_TIEN_R);
    _delay_ms(10);

    bao_cao(phat_xung_hai_ben(DIAG_PULSES),
            (uint16_t)(1000000UL / (2UL * DIAG_HALF_US)));

    dat(PIN_STEP_L, 0u);
    dat(PIN_STEP_R, 0u);
}
