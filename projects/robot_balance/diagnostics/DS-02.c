/* Phần đo của kịch bản DS-02 — kiểm cảm biến quán tính MPU6050.
 *
 * Tệp này là DỮ LIỆU CỦA DỰ ÁN: nó biết địa chỉ nào, thanh ghi nào, thang đo
 * nào. Bộ khung do Platform Pack cấp lo phần chung (bật UART, đóng gói khung).
 *
 * Hợp đồng với bộ khung, đúng hai hàm:
 *     void diag_run(void);          — hàm này định nghĩa
 *     void eaa_emit(const char *);  — bộ khung cấp, gửi một khung JSON
 *
 * Đo cái gì và VÌ SAO đo cái đó
 * ------------------------------
 * `who_am_i` trả lời câu rẻ nhất: có đúng con chip ta nghĩ không. Sai ở đây thì
 * mọi thanh ghi sau đều đọc nhầm bảng.
 *
 * `accel_noise_mg` và `gyro_noise_dps` đo NHIỄU NỀN khi robot đứng yên. Đây là
 * con số quyết định bộ lọc bù cần hằng số thời gian bao nhiêu, và nó chỉ đo
 * được trên đúng con chip đang cắm — datasheet cho dải điển hình, không cho
 * con số của mẫu này trên bo này.
 */

#include <stdint.h>
#include <avr/io.h>
#include <util/twi.h>

void eaa_emit(const char *json);

#define DIAG_TWI_SCL_HZ   400000UL
#define MPU_ADDR          0x68u
#define REG_WHO_AM_I      0x75u
#define REG_PWR_MGMT_1    0x6Bu
#define REG_ACCEL_XOUT_H  0x3Bu

/* Số mẫu lấy để ước lượng nhiễu nền. 100 mẫu ở 1 kHz là 0,1 giây — đủ để độ
 * lệch hội tụ, đủ ngắn để người cầm robot đứng yên được. */
#define DIAG_SAMPLES      100u

/* Hệ số thang đo mặc định sau khi reset: ±2 g và ±250 °/s. */
#define ACCEL_LSB_PER_G   16384L
#define GYRO_LSB_PER_DPS  131L

static void twi_init(void)
{
    TWSR = 0u;
    TWBR = (uint8_t)(((F_CPU / DIAG_TWI_SCL_HZ) - 16UL) / 2UL);
}

/* Chờ cờ TWINT có hạn đếm — firmware chẩn đoán treo thì không báo được rằng
 * nó treo, nên không có vòng chờ vô hạn nào ở đây. */
static uint8_t twi_cho(void)
{
    uint16_t han = 0u;
    while (!(TWCR & (1u << TWINT))) {
        if (++han == 0u) {
            return 0u;
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

static uint8_t twi_gui(uint8_t gia_tri)
{
    TWDR = gia_tri;
    TWCR = (1u << TWINT) | (1u << TWEN);
    return twi_cho();
}

static uint8_t twi_nhan(uint8_t ack, uint8_t *ra)
{
    TWCR = (uint8_t)((1u << TWINT) | (1u << TWEN) | (ack ? (1u << TWEA) : 0u));
    if (!twi_cho()) {
        return 0u;
    }
    *ra = TWDR;
    return 1u;
}

/* Đọc n byte liên tiếp từ thanh ghi đầu. Trả 0 nếu bất kỳ bước nào quá hạn. */
static uint8_t mpu_doc(uint8_t reg, uint8_t *dem, uint8_t n)
{
    if (!twi_start() || !twi_gui((uint8_t)(MPU_ADDR << 1)) || !twi_gui(reg)) {
        twi_stop();
        return 0u;
    }
    if (!twi_start() || !twi_gui((uint8_t)((MPU_ADDR << 1) | 1u))) {
        twi_stop();
        return 0u;
    }
    for (uint8_t i = 0u; i < n; i++) {
        if (!twi_nhan((uint8_t)(i + 1u < n), &dem[i])) {
            twi_stop();
            return 0u;
        }
    }
    twi_stop();
    return 1u;
}

static uint8_t mpu_ghi(uint8_t reg, uint8_t gia_tri)
{
    uint8_t ok = twi_start() && twi_gui((uint8_t)(MPU_ADDR << 1))
                 && twi_gui(reg) && twi_gui(gia_tri);
    twi_stop();
    return ok;
}

/* In một số nguyên có dấu vào bộ đệm, trả về số ký tự đã ghi. */
static uint8_t so_ra_chu(int32_t gia_tri, char *ra)
{
    char tam[12];
    uint8_t n = 0u, i = 0u;
    uint32_t duong;

    if (gia_tri < 0) {
        ra[i++] = '-';
        duong = (uint32_t)(-gia_tri);
    } else {
        duong = (uint32_t)gia_tri;
    }
    do {
        tam[n++] = (char)('0' + (duong % 10u));
        duong /= 10u;
    } while (duong != 0u);
    while (n != 0u) {
        ra[i++] = tam[--n];
    }
    return i;
}

/* Độ lệch trung bình tuyệt đối quanh giá trị trung bình.
 *
 * Dùng nó thay cho độ lệch chuẩn có chủ ý: nó chỉ cần phép cộng và phép chia
 * số nguyên, không cần căn bậc hai — và trên lõi 8 bit, một phép căn trong
 * firmware chẩn đoán là chi phí không đổi lấy được gì. Với nhiễu gần chuẩn,
 * hai đại lượng tỉ lệ với nhau, mà ở đây ta cần một con số so được với ngưỡng
 * chứ không cần một tham số thống kê đúng định nghĩa.
 */
static uint32_t do_lech_tb(const int16_t *mau, uint8_t n)
{
    int32_t tong = 0;
    uint32_t lech = 0u;
    int32_t trung_binh;

    for (uint8_t i = 0u; i < n; i++) {
        tong += mau[i];
    }
    trung_binh = tong / (int32_t)n;
    for (uint8_t i = 0u; i < n; i++) {
        int32_t d = (int32_t)mau[i] - trung_binh;
        lech += (uint32_t)(d < 0 ? -d : d);
    }
    return lech / (uint32_t)n;
}

void diag_run(void)
{
    uint8_t dem[14];
    char khung[96];
    uint8_t i;
    int16_t ax[DIAG_SAMPLES];
    int16_t gx[DIAG_SAMPLES];
    uint16_t thu = 0u;

    twi_init();

    if (!mpu_doc(REG_WHO_AM_I, dem, 1u)) {
        /* Nói rõ "không đọc được" thay vì im lặng: im lặng không phân biệt
         * được với firmware treo hay dây UART đứt. */
        eaa_emit("{\"who_am_i\": null, \"error\": \"khong doc duoc\"}");
        return;
    }

    i = 0u;
    {
        static const char bang[] = "0123456789abcdef";
        const char *dau = "{\"who_am_i\": \"0x";
        while (*dau != '\0') {
            khung[i++] = *dau++;
        }
        khung[i++] = bang[(dem[0] >> 4) & 0x0Fu];
        khung[i++] = bang[dem[0] & 0x0Fu];
        khung[i++] = '"';
        khung[i++] = '}';
        khung[i] = '\0';
    }
    eaa_emit(khung);

    /* Đánh thức chip: sau reset nó ở chế độ ngủ và mọi số đọc về đều là 0 —
     * một loạt số 0 trông y hệt một cảm biến đứng rất yên. */
    (void)mpu_ghi(REG_PWR_MGMT_1, 0x00u);

    for (i = 0u; i < DIAG_SAMPLES; i++) {
        if (!mpu_doc(REG_ACCEL_XOUT_H, dem, 14u)) {
            break;
        }
        ax[i] = (int16_t)(((uint16_t)dem[0] << 8) | dem[1]);
        gx[i] = (int16_t)(((uint16_t)dem[8] << 8) | dem[9]);
        thu++;
    }

    {
        uint32_t nhieu_a = thu ? do_lech_tb(ax, (uint8_t)thu) : 0u;
        uint32_t nhieu_g = thu ? do_lech_tb(gx, (uint8_t)thu) : 0u;
        /* Quy về đơn vị vật lý bằng số nguyên: mg và phần trăm độ/giây.
         * Nhân trước chia sau để không mất phần lẻ ở lõi không có dấu phẩy
         * động — thứ tự này là lý do con số ra được, không phải chi tiết vụn. */
        /* mg NHÂN 100 — giữ hai chữ số thập phân, đúng như đường con quay
         * ngay dưới đã làm.
         *
         * Bản trước tính thẳng ra mg nguyên. Nhiễu nền lành mạnh của con chip
         * này khi nằm yên là 4-8 LSB, tức 0,2-0,5 mg, nên nó LÀM TRÒN THÀNH 0.
         * Và số 0 ấy không phân biệt được "cảm biến rất yên" với "cảm biến
         * không đọc được" — đúng cái bẫy mà chú thích ở đầu tệp này đã nêu:
         * chip còn ngủ thì mọi số đọc về đều là 0 và trông y hệt.
         *
         * Một phép đo mà đơn vị của nó thô hơn đại lượng cần đo thì nó không
         * đo gì cả. */
        uint32_t mg_x100 = (nhieu_a * 100000u) / (uint32_t)ACCEL_LSB_PER_G;
        uint32_t dps_x100 = (nhieu_g * 100u) / (uint32_t)GYRO_LSB_PER_DPS;

        i = 0u;
        const char *k1 = "{\"samples\": ";
        while (*k1 != '\0') { khung[i++] = *k1++; }
        i += so_ra_chu((int32_t)thu, &khung[i]);
        const char *k2 = ", \"accel_noise_mg\": ";
        while (*k2 != '\0') { khung[i++] = *k2++; }
        i += so_ra_chu((int32_t)(mg_x100 / 100u), &khung[i]);
        khung[i++] = '.';
        khung[i++] = (char)('0' + (char)((mg_x100 / 10u) % 10u));
        khung[i++] = (char)('0' + (char)(mg_x100 % 10u));
        const char *k3 = ", \"gyro_noise_dps\": ";
        while (*k3 != '\0') { khung[i++] = *k3++; }
        i += so_ra_chu((int32_t)(dps_x100 / 100u), &khung[i]);
        khung[i++] = '.';
        khung[i++] = (char)('0' + (char)((dps_x100 / 10u) % 10u));
        khung[i++] = (char)('0' + (char)(dps_x100 % 10u));
        khung[i++] = '}';
        khung[i] = '\0';
    }
    eaa_emit(khung);
}
