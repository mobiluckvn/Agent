/* Phần đo của kịch bản DS-01 — quét bus I2C.
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN, không phải của engine: nó biết bus nào, thanh
 * ghi nào, địa chỉ nào — đúng những thứ engine không được biết. Bộ khung do
 * Platform Pack cấp lo phần chung (bật UART, đóng gói khung, gọi hàm dưới đây).
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);          — hàm này định nghĩa
 *     void eaa_emit(const char *);  — bộ khung cấp, gửi một khung JSON
 *
 * Kịch bản này rẻ nhất và nên chạy đầu tiên: nếu cảm biến không trả lời ở đây
 * thì mọi kết luận về dữ liệu của nó đều vô nghĩa.
 */

#include <stdint.h>
#include <avr/io.h>
#include <util/twi.h>

void eaa_emit(const char *json);

/* Tần số bus 100 kHz — chậm hơn fast-mode của hồ sơ phần cứng có chủ ý: quét
 * bus là lúc ta CHƯA biết đường truyền có tốt không, nên đi chậm cho chắc. */
#define DIAG_TWI_SCL_HZ 100000UL

static void twi_init(void)
{
    TWSR = 0u;   /* hệ số chia tần = 1 */
    TWBR = (uint8_t)(((F_CPU / DIAG_TWI_SCL_HZ) - 16UL) / 2UL);
}

/* Chờ cờ TWINT với hạn đếm — KHÔNG chờ vô hạn.
 *
 * Đây chính là điều ràng buộc blocking_io cấm ở firmware sản phẩm, và lý do
 * cấm hiện rõ nhất ở đúng kịch bản này: một thiết bị giữ bus thấp sẽ treo vòng
 * chờ mãi mãi, và firmware chẩn đoán treo thì không báo được rằng nó treo. */
static uint8_t twi_cho(void)
{
    uint16_t han = 0u;
    while (!(TWCR & (1u << TWINT))) {
        if (++han == 0u) {
            return 0u;   /* quá hạn */
        }
    }
    return 1u;
}

static uint8_t twi_start(void)
{
    TWCR = (1u << TWINT) | (1u << TWSTA) | (1u << TWEN);
    return twi_cho();
}

static void twi_stop(void)
{
    TWCR = (1u << TWINT) | (1u << TWSTO) | (1u << TWEN);
}

/* Gửi địa chỉ + bit ghi, trả 1 nếu thiết bị trả lời ACK. */
static uint8_t twi_do_dia_chi(uint8_t dia_chi)
{
    if (!twi_start()) {
        return 0u;
    }
    TWDR = (uint8_t)(dia_chi << 1);
    TWCR = (1u << TWINT) | (1u << TWEN);
    if (!twi_cho()) {
        twi_stop();
        return 0u;
    }
    uint8_t trang_thai = (uint8_t)(TWSR & 0xF8u);
    twi_stop();
    return (uint8_t)(trang_thai == TW_MT_SLA_ACK);
}

static void gui_dia_chi(uint8_t dia_chi)
{
    static const char bang[] = "0123456789abcdef";
    char khung[32];
    uint8_t i = 0u;

    const char *dau = "{\"i2c_addresses\": [\"0x";
    while (*dau != '\0') {
        khung[i++] = *dau++;
    }
    khung[i++] = bang[(dia_chi >> 4) & 0x0Fu];
    khung[i++] = bang[dia_chi & 0x0Fu];
    khung[i++] = '"';
    khung[i++] = ']';
    khung[i++] = '}';
    khung[i] = '\0';

    eaa_emit(khung);
}

void diag_run(void)
{
    uint8_t dem = 0u;

    twi_init();

    /* Dải địa chỉ 7 bit hợp lệ; 0x00-0x07 và 0x78-0x7F là dành riêng. */
    for (uint8_t dia_chi = 0x08u; dia_chi <= 0x77u; dia_chi++) {
        if (twi_do_dia_chi(dia_chi)) {
            gui_dia_chi(dia_chi);
            dem++;
        }
    }

    if (dem == 0u) {
        /* Nói rõ "quét xong, không ai trả lời" — khác hẳn với việc im lặng,
         * vốn không phân biệt được với firmware treo hay dây UART đứt. */
        eaa_emit("{\"i2c_addresses\": []}");
    }
}
