"""TC-11, TC-14 — adapter mô hình thật, hoán đổi được và không rò khóa.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-11 | Hoán đổi model | đổi provider → hành vi Orchestrator KHÔNG đổi; chỉ trường `llm_model` trong chỉ số đổi |
| TC-14 | Bảo mật khóa API | khóa không xuất hiện ở BẤT KỲ đầu ra nào — log, ngoại lệ, `repr`, nhật ký lời gọi |

Bộ test này chạy KHÔNG cần khóa thật: lớp vận chuyển HTTP được tiêm vào, nên
mọi nhánh xử lý phản hồi và lỗi đều kiểm được tất định. Điều nó chứng minh là
*adapter xử lý đúng những gì nhà cung cấp trả về*; nó không chứng minh nhà cung
cấp hôm nay trả về như vậy — đó là việc của TC-15 với khóa thật.

TC-14 đáng được canh gắt: một khóa lọt vào nhật ký hay vào thông báo lỗi rồi
được dán vào báo cáo lỗi là chuyện xảy ra thường xuyên, và không thể thu hồi.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eaa.llm.base import BudgetExceeded, LLMError, Prompt, PromptLayer
from eaa.llm.calllog import CallLog, ReplayClient, ReplayMiss
from eaa.llm.gemini import (
    API_KEY_ENV,
    DEFAULT_MODEL,
    GeminiClient,
    GeminiError,
    MissingApiKey,
    ModelNotFound,
)
from eaa.llm.mock import MockLLM

KHOA_GIA = "AIzaSyKHOA-BI-MAT-KHONG-DUOC-LO-RA-DAU-CA-123456"

MA_TRA_VE = """```file:src/m.c
#include "m.h"

// ref: ds-021
void m_init(void)
{
    static uint8_t n;
    n = 0u;
}
```
"""


def _prompt(**ghi_de) -> Prompt:
    mac_dinh = dict(
        system_instruction="Bạn là kỹ sư firmware. CẤM delay().",
        layers=[
            PromptLayer("task", "Viết module đọc cảm biến.", budget=500, required=True)
        ],
        module="drv_bus_sensor",
        constraints_version="sha256:ab12",
        chunk_ids=("ds-021",),
    )
    mac_dinh.update(ghi_de)
    return Prompt(**mac_dinh)


def _phan_hoi(van_ban: str = MA_TRA_VE, **ghi_de) -> dict:
    mac_dinh = {
        "candidates": [
            {"content": {"parts": [{"text": van_ban}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 1234, "candidatesTokenCount": 88},
    }
    mac_dinh.update(ghi_de)
    return mac_dinh


class GiaLapMang:
    """Lớp vận chuyển giả — ghi lại mọi thứ adapter định gửi đi."""

    def __init__(self, *phan_hoi, loi=None):
        self.phan_hoi = list(phan_hoi) or [_phan_hoi()]
        self.loi = loi
        self.yeu_cau: list[dict] = []

    @staticmethod
    def body_contents(than: bytes):
        return json.loads(than.decode("utf-8")).get("contents", [])

    def __call__(self, url: str, than: bytes, api_key: str, timeout: float):
        self.yeu_cau.append(
            {
                "url": url,
                "body": json.loads(than.decode("utf-8")),
                "api_key": api_key,
                "timeout": timeout,
            }
        )
        if self.loi is not None:
            raise self.loi
        if "countTokens" in url:
            # Đếm theo độ dài thật, không trả hằng số: một bộ đếm giả trả cùng
            # một số cho mọi lớp sẽ làm phép kiểm ngân sách vô nghĩa.
            van_ban = "".join(
                p.get("text", "")
                for c in self.body_contents(than)
                for p in c.get("parts", [])
            )
            return {"totalTokens": max(1, len(van_ban) // 4)}
        return self.phan_hoi[min(len(self.yeu_cau) - 1, len(self.phan_hoi) - 1)]


@pytest.fixture()
def co_khoa(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(API_KEY_ENV, KHOA_GIA)


@pytest.fixture()
def client(co_khoa) -> GeminiClient:
    return GeminiClient(model="gemini-pro-3.1", transport=GiaLapMang())


# --------------------------------------------------------------------------
# Cấu hình theo AIS §2
# --------------------------------------------------------------------------


def test_gui_dung_cau_hinh_cua_AIS(client: GeminiClient) -> None:
    client.generate(_prompt())
    than = client.transport.yeu_cau[-1]["body"]

    assert than["generationConfig"]["temperature"] == 0.2, "sinh mã cần tất định"
    assert than["generationConfig"]["maxOutputTokens"] == 200_000
    assert than["generationConfig"]["candidateCount"] == 1


def test_rang_buoc_di_vao_systemInstruction_khong_lan_vao_noi_dung(
    client: GeminiClient,
) -> None:
    """AIS §2: nhà cung cấp tách hai phần này — tận dụng để ràng buộc không trôi."""
    client.generate(_prompt())
    than = client.transport.yeu_cau[-1]["body"]

    assert "CẤM delay()" in than["systemInstruction"]["parts"][0]["text"]
    assert "CẤM delay()" not in than["contents"][0]["parts"][0]["text"]


def test_ma_model_duoc_ghim_trong_duong_dan(client: GeminiClient) -> None:
    client.generate(_prompt())
    assert "models/gemini-pro-3.1:generateContent" in client.transport.yeu_cau[-1]["url"]
    assert "latest" not in client.transport.yeu_cau[-1]["url"]


def test_ngan_sach_kiem_TRUOC_khi_goi(co_khoa) -> None:
    mang = GiaLapMang()
    client = GeminiClient(transport=mang)
    # Phải vượt TRẦN TỔNG theo bộ đếm CỦA MÔ HÌNH (giả lập: len//4), không chỉ
    # vượt phần của lớp — phép chặn theo lớp nay chỉ ghi lại (SL-161).
    # 40.000 ký tự → 10.000 token > trần 8.000.
    qua_dai = _prompt(layers=[PromptLayer("task", "x " * 20000, budget=500)])

    with pytest.raises(BudgetExceeded):
        client.generate(qua_dai)

    assert not any(
        "generateContent" in r["url"] for r in mang.yeu_cau
    ), "đã gọi sinh nội dung dù prompt vượt ngân sách"


def test_dem_token_dung_bo_dem_cua_mo_hinh(client: GeminiClient) -> None:
    ngan = client.count_tokens("ngắn")
    dai = client.count_tokens("dài " * 200)
    assert dai > ngan > 0
    assert any("countTokens" in r["url"] for r in client.transport.yeu_cau)


def test_khong_goi_duoc_thi_lui_ve_uoc_luong_ngoai_tuyen(monkeypatch) -> None:
    """Hậu quả xấu nhất là chặn nhầm một prompt hợp lệ — chấp nhận được."""
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    client = GeminiClient()
    assert client.count_tokens("một hai ba bốn") > 0


# --------------------------------------------------------------------------
# TC-14 — khóa API không rò ra bất kỳ đâu
# --------------------------------------------------------------------------


def test_tc14_thieu_khoa_bao_loi_ro_rang(monkeypatch) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(MissingApiKey, match=API_KEY_ENV):
        GeminiClient(transport=GiaLapMang()).generate(_prompt())


def test_tc14_repr_khong_chua_khoa(client: GeminiClient) -> None:
    """repr xuất hiện trong vết ngăn xếp và đầu ra pytest — hai nơi hay bị dán."""
    client.api_key  # nạp khóa vào bộ nhớ
    van_ban = repr(client)
    assert KHOA_GIA not in van_ban
    assert "api_key=***" in van_ban


def test_tc14_khoa_khong_lot_vao_thong_bao_loi_HTTP(co_khoa) -> None:
    import urllib.error
    import io

    loi = urllib.error.HTTPError(
        url=f"https://x/?key={KHOA_GIA}",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=io.BytesIO(
            json.dumps({"error": {"message": f"api_key: {KHOA_GIA} không hợp lệ"}}).encode()
        ),
    )
    client = GeminiClient(transport=GiaLapMang(loi=loi))

    with pytest.raises(GeminiError) as thong_tin:
        client.generate(_prompt())
    assert KHOA_GIA not in str(thong_tin.value)


def test_tc14_khoa_khong_lot_vao_nhat_ky_loi_goi(co_khoa, tmp_path: Path) -> None:
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    client = GeminiClient(transport=GiaLapMang(), call_log=nhat_ky)

    client.generate(_prompt(system_instruction=f"Xác thực bằng {KHOA_GIA}"))

    noi_dung = nhat_ky.path.read_text(encoding="utf-8")
    assert KHOA_GIA not in noi_dung
    assert "***" in noi_dung


def test_tc14_khoa_khong_lot_vao_bam_prompt(co_khoa) -> None:
    lo_mang = _prompt(system_instruction=f"Xác thực bằng {KHOA_GIA}")
    da_che = _prompt(system_instruction="Xác thực bằng ***")
    assert lo_mang.hash == da_che.hash


def test_tc14_khoa_chi_doc_tu_bien_moi_truong() -> None:
    """Không nhận qua tham số: khóa truyền qua dòng lệnh nằm lại trong lịch sử shell."""
    import inspect

    tham_so = inspect.signature(GeminiClient.__init__).parameters
    mang_bi_mat = {"key", "api_key", "apikey", "token", "secret", "password", "credential"}
    dang_ngo = [
        t
        for t in tham_so
        if t in mang_bi_mat or t.endswith(("_key", "_secret", "_password"))
    ]
    assert not dang_ngo, f"hàm dựng nhận khóa qua tham số: {dang_ngo}"


# --------------------------------------------------------------------------
# Xử lý lỗi — SDD §6
# --------------------------------------------------------------------------


def test_ma_model_khong_ton_tai_bao_dung_van_de(co_khoa) -> None:
    import io
    import urllib.error

    loi = urllib.error.HTTPError(
        url="https://x", code=404, msg="Not Found", hdrs=None,
        fp=io.BytesIO(b'{"error":{"message":"model not found"}}'),
    )
    client = GeminiClient(model="gemini-khong-co-that", transport=GiaLapMang(loi=loi))

    with pytest.raises(ModelNotFound, match="eaa init --model"):
        client.generate(_prompt())


def test_khoa_bi_tu_choi_bao_dung_van_de(co_khoa) -> None:
    import io
    import urllib.error

    loi = urllib.error.HTTPError(
        url="https://x", code=403, msg="Forbidden", hdrs=None, fp=io.BytesIO(b"{}")
    )
    with pytest.raises(GeminiError, match=API_KEY_ENV):
        GeminiClient(transport=GiaLapMang(loi=loi)).generate(_prompt())


def test_mo_hinh_tu_choi_prompt_bao_ro_ly_do(client: GeminiClient) -> None:
    client.transport.phan_hoi = [
        {"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []}
    ]
    with pytest.raises(GeminiError, match="SAFETY"):
        client.generate(_prompt())


def test_phan_hoi_bi_cat_cut_thi_bao_chia_nho_module(client: GeminiClient) -> None:
    """Trần token đặt rất cao, nên chạm trần là dấu hiệu module quá lớn."""
    client.transport.phan_hoi = [
        _phan_hoi(candidates=[{"content": {"parts": [{"text": "x"}]}, "finishReason": "MAX_TOKENS"}])
    ]
    with pytest.raises(GeminiError, match="chia nhỏ module"):
        client.generate(_prompt())


def test_phan_hoi_rong_tinh_la_mot_lan_fail_vong_tu_sua(client: GeminiClient) -> None:
    client.transport.phan_hoi = [
        _phan_hoi(candidates=[{"content": {"parts": []}, "finishReason": "STOP"}])
    ]
    with pytest.raises(GeminiError, match="vòng tự sửa"):
        client.generate(_prompt())


def test_phan_hoi_sai_dinh_dang_tinh_la_mot_lan_fail(client: GeminiClient) -> None:
    client.transport.phan_hoi = [_phan_hoi("Đây là văn xuôi, không có khối file.")]
    with pytest.raises(LLMError, match="fail của vòng tự sửa"):
        client.generate(_prompt())


# --------------------------------------------------------------------------
# TC-11 — hoán đổi model không đổi hành vi Orchestrator
# --------------------------------------------------------------------------


def test_tc11_hai_adapter_cung_giao_dien(co_khoa) -> None:
    from eaa.llm.base import LLMClient

    for client in (MockLLM(), GeminiClient(transport=GiaLapMang()), ReplayClient(CallLog("x"))):
        assert isinstance(client, LLMClient)


def test_tc11_doi_adapter_thi_artifact_van_du_dau_vet_truy_vet(co_khoa) -> None:
    """Chỉ trường model đổi; mọi dấu vết NFR-07 khác giữ nguyên cấu trúc."""
    prompt = _prompt()

    a = MockLLM().generate(prompt)
    b = GeminiClient(model="gemini-pro-3.1", transport=GiaLapMang()).generate(prompt)

    assert a.prompt_hash == b.prompt_hash == prompt.hash
    assert a.constraints_version == b.constraints_version
    assert a.chunk_ids == b.chunk_ids
    assert a.model != b.model
    assert b.model == "gemini-pro-3.1"
    assert a.files and b.files


def test_tc11_so_lieu_token_ghi_tu_nha_cung_cap(client: GeminiClient) -> None:
    """Số token lấy từ nhà cung cấp, không tự ước lượng — chi phí phải đúng."""
    artifact = client.generate(_prompt())
    assert artifact.tokens_in == 1234
    assert artifact.tokens_out == 88


# --------------------------------------------------------------------------
# Nhật ký lời gọi và phát lại
# --------------------------------------------------------------------------


def test_moi_loi_goi_duoc_ghi_lam_bang_chung(co_khoa, tmp_path: Path) -> None:
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    GeminiClient(transport=GiaLapMang(), call_log=nhat_ky).generate(_prompt())

    ban_ghi = nhat_ky.all()
    assert len(ban_ghi) == 1
    assert ban_ghi[0].prompt_hash == _prompt().hash
    # So với DEFAULT_MODEL chứ không với một chuỗi gõ tay: bài này canh việc
    # "mã model có được ghi vào bằng chứng không", không canh việc "mặc định
    # đang là model nào". Đổi mặc định (SL-170) không được làm bài này đỏ.
    assert ban_ghi[0].model == DEFAULT_MODEL
    assert ban_ghi[0].module == "drv_bus_sensor"
    assert ban_ghi[0].chunk_ids == ("ds-021",)


def test_phat_lai_tra_dung_phan_hoi_da_ghi(co_khoa, tmp_path: Path) -> None:
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    that = GeminiClient(transport=GiaLapMang(), call_log=nhat_ky).generate(_prompt())

    phat_lai = ReplayClient(nhat_ky).generate(_prompt())

    assert phat_lai.files == that.files
    assert phat_lai.model == that.model, "phát lại giữ nguyên mã model để truy vết"
    assert phat_lai.prompt_hash == that.prompt_hash


def test_phat_lai_KHONG_bia_phan_hoi_khi_thieu_ban_ghi(tmp_path: Path) -> None:
    """Một lượt phát lại tự sinh nội dung sẽ tạo bằng chứng giả cho Chương 3."""
    with pytest.raises(ReplayMiss, match="KHÔNG bịa phản hồi"):
        ReplayClient(CallLog(tmp_path / "trong.jsonl")).generate(_prompt())


def test_phat_hien_mo_hinh_doi_hanh_vi_giua_ky(tmp_path: Path) -> None:
    """Rủi ro R1: cùng băm prompt mà hai phản hồi khác nhau."""
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    prompt = _prompt()

    nhat_ky.record(prompt=prompt, response=MA_TRA_VE, model="gemini-pro-3.1")
    assert nhat_ky.drift() == []

    nhat_ky.record(
        prompt=prompt,
        response=MA_TRA_VE.replace("n = 0u;", "n = 1u;"),
        model="gemini-pro-3.1",
    )
    troi = nhat_ky.drift()
    assert len(troi) == 1 and troi[0][0] == prompt.hash
    assert nhat_ky.summary()["drifted_prompts"] == 1


def test_tong_hop_nhat_ky_du_so_lieu_cho_chuong_3(co_khoa, tmp_path: Path) -> None:
    nhat_ky = CallLog(tmp_path / "llm_calls.jsonl")
    client = GeminiClient(transport=GiaLapMang(), call_log=nhat_ky)
    client.generate(_prompt())
    client.generate(_prompt(module="pid_controller"))

    tom_tat = nhat_ky.summary()
    assert tom_tat["calls"] == 2
    assert tom_tat["modules"] == ["drv_bus_sensor", "pid_controller"]
    assert tom_tat["models"] == [DEFAULT_MODEL]
    assert tom_tat["tokens_in_total"] == 2 * 1234


def test_ban_ghi_hong_bao_loi_kem_so_dong(tmp_path: Path) -> None:
    path = tmp_path / "llm_calls.jsonl"
    path.write_text('{"prompt_hash":"a"}\nkhong-phai-json\n', encoding="utf-8")
    with pytest.raises(LLMError, match=":2:"):
        CallLog(path).all()


# --------------------------------------------------------------------------
# Trần token đầu ra — AIS §2: hiệu lực = min(cấu hình, trần thật của model)
# --------------------------------------------------------------------------


def test_tran_token_ra_bi_kep_theo_tran_that_cua_model(co_khoa) -> None:
    """Không phải phòng xa: model thật có trần 65.536, cấu hình đòi 200.000."""
    client = GeminiClient(
        transport=GiaLapMang(),
        metadata_transport=lambda url, key, timeout: {"outputTokenLimit": 65536},
    )
    assert client.output_limit() == 65_536

    client.generate(_prompt())
    than = client.transport.yeu_cau[-1]["body"]
    assert than["generationConfig"]["maxOutputTokens"] == 65_536


def test_khong_tra_duoc_tran_thi_giu_cau_hinh_va_de_nha_cung_cap_bao_loi(
    co_khoa,
) -> None:
    """Thà một thông báo lỗi rõ từ họ còn hơn ta tự đoán rồi cắt cụt phản hồi."""

    def hong(url, key, timeout):
        raise OSError("mạng hỏng")

    client = GeminiClient(transport=GiaLapMang(), metadata_transport=hong)
    assert client.output_limit() == 200_000


def test_tiem_lop_van_chuyen_thi_KHONG_cham_mang(co_khoa) -> None:
    """Bài test dùng lớp giả không được lặng lẽ gọi ra ngoài hỏi trần token."""
    client = GeminiClient(transport=GiaLapMang())
    assert client.output_limit() == 200_000
    assert not any("outputToken" in str(r) for r in client.transport.yeu_cau)


def test_tran_chi_tra_mot_lan_roi_nho(co_khoa) -> None:
    dem = {"n": 0}

    def lay(url, key, timeout):
        dem["n"] += 1
        return {"outputTokenLimit": 65536}

    client = GeminiClient(transport=GiaLapMang(), metadata_transport=lay)
    client.output_limit()
    client.output_limit()
    assert dem["n"] == 1
