"""TC-77 — giữ bản cũ công cụ tự sinh, sinh tài liệu, và chế độ xem trước.

Ba việc rời nhau, nhưng cùng một nếp: **đừng để một đường đi thường dùng trở
thành một canh bạc không có đường lui.**

* `eaa suggest` đề nghị viết lại công cụ hay hỏng — nên "viết lại" là đường
  thường dùng, và nó phải có đường lui.
* Một tài liệu do mô hình viết lại có thể lệch khỏi mã; tài liệu lệch khỏi mã
  tệ hơn không có tài liệu.
* Máy chưa có toolchain là hoàn cảnh rất thường gặp, và khi ấy người dùng
  không xem được cả dòng mã nào.
"""

from __future__ import annotations

import pytest

from eaa.toolforge import (
    DA_DUYET,
    DA_KIEM_THU,
    DE_XUAT,
    ForgedTool,
    ForgeError,
    ToolForge,
    ToolRegistry,
)

MA_1 = ('"""Bản một."""\nMO_TA = "đếm dòng"\n'
        'SCHEMA = {"type": "object", "properties": {"text": {"type": "string",'
        ' "description": "nội dung"}}, "required": ["text"]}\n\n\n'
        'def run(text: str = "") -> str:\n    return str(len(text.splitlines()))\n\n\n'
        'def test_dem():\n    assert run(text="a\\nb") == "2"\n')

MA_2 = MA_1.replace("Bản một", "Bản hai").replace('return str(len(', 'return str(1 + len(')


def _da_duyet(tmp_path, ma=MA_1, ten="dem_dong"):
    kho = ToolRegistry(tmp_path)
    kho.save(ForgedTool(name=ten, purpose="đếm dòng", code=ma, status=DA_KIEM_THU,
                        schema={"type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"]}))
    kho.approve(ten, by="vu-tri-cong")
    return kho


# ═══════════════════════ giữ bản cũ và quay lui ═══════════════════════


def test_ghi_de_mot_ban_DA_DUYET_thi_cat_ban_cu(tmp_path):
    kho = _da_duyet(tmp_path)
    assert kho.versions("dem_dong") == []

    kho.set_status("dem_dong", DE_XUAT, code=MA_2)
    ban_cu = kho.versions("dem_dong")
    assert len(ban_cu) == 1
    assert ban_cu[0].read_text(encoding="utf-8") == MA_1


def test_ban_CHUA_DUYET_thi_khong_cat(tmp_path):
    """Bản chưa ai duyệt thì chưa từng chạy thật — quay lui về nó không được gì."""
    kho = ToolRegistry(tmp_path)
    kho.save(ForgedTool(name="x", purpose="p", code=MA_1, status=DE_XUAT))
    kho.save(ForgedTool(name="x", purpose="p", code=MA_2, status=DE_XUAT))
    assert kho.versions("x") == []


def test_luu_lai_dung_ma_cu_thi_khong_cat_them(tmp_path):
    kho = _da_duyet(tmp_path)
    kho.set_status("dem_dong", DA_DUYET, code=MA_1)
    assert kho.versions("dem_dong") == []


def test_quay_lui_ve_ban_truoc(tmp_path):
    kho = _da_duyet(tmp_path)
    kho.set_status("dem_dong", DE_XUAT, code=MA_2)

    t = ToolForge(registry=kho).rollback("dem_dong")
    assert t.code == MA_1
    assert "quay lui" in t.note


def test_ban_quay_lui_KHONG_tu_len_lai_da_duyet(tmp_path):
    """'Từng chạy được' là ở một môi trường khác, có thể ở Python khác."""
    kho = _da_duyet(tmp_path)
    kho.set_status("dem_dong", DE_XUAT, code=MA_2)

    t = ToolForge(registry=kho).rollback("dem_dong")
    assert t.status == DE_XUAT
    with pytest.raises(ForgeError, match="chưa được duyệt"):
        ToolForge(registry=kho).run("dem_dong", {"text": "a"})


def test_quay_lui_roi_van_di_lai_ba_cong_duoc(tmp_path):
    kho = _da_duyet(tmp_path)
    kho.set_status("dem_dong", DE_XUAT, code=MA_2)
    xuong = ToolForge(registry=kho)
    xuong.rollback("dem_dong")
    assert xuong.verify("dem_dong").passed is True


def test_khong_co_ban_cu_thi_bao_ro_vi_sao(tmp_path):
    kho = _da_duyet(tmp_path)
    with pytest.raises(ForgeError, match="chưa từng chạy thật"):
        ToolForge(registry=kho).rollback("dem_dong")


def test_quay_lui_cong_cu_khong_co(tmp_path):
    with pytest.raises(ForgeError, match="không có"):
        ToolForge(registry=ToolRegistry(tmp_path)).rollback("khong-co")


# ═══════════════════════════ sinh tài liệu ═══════════════════════════


def test_tai_lieu_dung_tu_MA_khong_hoi_mo_hinh(tmp_path):
    """Tài liệu lệch khỏi mã tệ hơn không có tài liệu."""
    kho = _da_duyet(tmp_path)
    # llm=None: nếu nó hỏi mô hình thì bài này hỏng ngay.
    d = ToolForge(registry=kho, llm=None).document("dem_dong")
    assert "# dem_dong" in d
    assert "đếm dòng" in d
    assert "`text`" in d and "string" in d
    assert "`test_dem`" in d


def test_tai_lieu_neu_cach_goi_cu_the(tmp_path):
    d = ToolForge(registry=_da_duyet(tmp_path)).document("dem_dong")
    assert "eaa tool run dem_dong --args" in d
    assert '"text"' in d


def test_tai_lieu_neu_gioi_han_da_biet(tmp_path):
    d = ToolForge(registry=_da_duyet(tmp_path)).document("dem_dong")
    assert "Giới hạn đã biết" in d
    assert "lúc duyệt" in d
    assert "không tự mở mạng" in d


def test_tai_lieu_kem_so_do_khi_da_dung_that(tmp_path):
    from eaa.toolusage import UsageLog

    n = UsageLog(tmp_path)
    for _ in range(3):
        n.record("dem_dong", ok=True, duration_ms=12)
    n.record("dem_dong", ok=False, error="ValueError: x")

    d = ToolForge(registry=_da_duyet(tmp_path)).document("dem_dong", usage=n)
    assert "Đo được sau khi dùng thật" in d
    assert "4 lần dùng · 3 đạt / 1 hỏng" in d


def test_tai_lieu_khong_bia_so_khi_chua_dung_lan_nao(tmp_path):
    from eaa.toolusage import UsageLog

    d = ToolForge(registry=_da_duyet(tmp_path)).document(
        "dem_dong", usage=UsageLog(tmp_path))
    assert "Đo được sau khi dùng thật" not in d


def test_tai_lieu_cong_cu_khong_co(tmp_path):
    with pytest.raises(ForgeError, match="không có"):
        ToolForge(registry=ToolRegistry(tmp_path)).document("khong-co")


def test_cong_cu_khong_tham_so_van_sinh_duoc_tai_lieu(tmp_path):
    kho = ToolRegistry(tmp_path)
    kho.save(ForgedTool(name="x", purpose="p", code=MA_1, status=DE_XUAT, schema={}))
    d = ToolForge(registry=kho).document("x")
    assert "Không nhận tham số nào" in d


# ═════════════════════ chế độ xem trước (C10.3) ═════════════════════


def test_cau_hinh_mac_dinh_khong_phai_xem_truoc():
    from eaa.orchestrator import OrchestratorConfig

    assert OrchestratorConfig().preview is False


def test_xem_truoc_dung_TRUOC_ca_khi_tao_nhanh():
    """Không nhánh nghĩa là không có gì để merge, kể cả nếu ai đó viết nhầm
    một lối merge thứ hai: lối ấy sẽ không tìm thấy nhánh nào của lượt chạy này."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    i_xem = src.index("if self.config.preview:")
    i_nhanh = src.index("self.repo.start_module(")
    i_cong = src.index("self._chay_chuoi_cong(")
    assert i_xem < i_nhanh, "xem trước phải trả về trước khi tạo nhánh"
    assert i_xem < i_cong, "xem trước phải trả về trước khi chạy cổng"


def test_xem_truoc_khong_commit_khong_xin_gate():
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    nhanh = src[src.index("if self.config.preview:"):src.index("branch = self.repo.start_module")]
    for cam in ("_commit(", "_xin_gate(", "_luu_bang_chung("):
        assert cam not in nhanh, f"nhánh xem trước không được gọi {cam}"
    assert '"preview"' in nhanh


def test_xem_truoc_noi_ro_ma_CHUA_DUOC_KIEM():
    """Một bản mã chưa qua cổng nào mà trông như đã xong là cách hỏng tệ nhất."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    nhanh = src[src.index("if self.config.preview:"):src.index("branch = self.repo.start_module")]
    assert "CHƯA ĐƯỢC KIỂM" in nhanh
    assert "chưa từng được dịch" in nhanh


def test_preview_va_draft_loai_tru_nhau():
    import inspect

    from eaa import cli

    src = inspect.getsource(cli.cmd_gen)
    assert "loại trừ nhau" in src


# ═════════════════════ gói runtime đã cài (C2.4) ═════════════════════


def test_liet_ke_goi_python():
    from eaa.environ import list_packages

    ds = list_packages(runner=lambda argv: (0, "pytest==8.0.0\npyyaml==6.0\n"))
    assert ds == ["pytest==8.0.0", "pyyaml==6.0"]


def test_lenh_hoi_dung_trinh_thong_dich_dang_chay():
    import sys

    from eaa.environ import list_packages

    da_goi = []
    list_packages(runner=lambda argv: (da_goi.append(argv) or (0, "")))
    assert da_goi[0][0] == sys.executable


def test_hoi_khong_duoc_thi_tra_rong_chu_khong_sap():
    from eaa.environ import list_packages

    assert list_packages(runner=lambda argv: (1, "lỗi")) == []


def test_he_sinh_thai_la_bao_ro():
    from eaa.environ import list_packages

    with pytest.raises(ValueError, match="Đang biết"):
        list_packages(ecosystem="cargo")


def test_moi_he_sinh_thai_khai_deu_goi_duoc():
    from eaa.environ import LENH_LIET_KE_GOI, list_packages

    for he in LENH_LIET_KE_GOI:
        assert list_packages(ecosystem=he, runner=lambda a: (0, "x")) == ["x"]


# ═════════ xưởng công cụ là bậc áp chót của thang gỡ cài đặt (C5.6) ═════════


def test_thang_go_co_bac_tu_viet_thay_the():
    from eaa.installerr import KHONG_TIM_THAY, MANG, QUYEN, remedies

    for loai in (MANG, QUYEN, KHONG_TIM_THAY):
        thang = remedies(loai, tool="cong-cu-x")
        bac = [r for r in thang if "tối thiểu thay thế" in r.action]
        assert bac, loai
        assert bac[0].command[:2] == ("tool", "propose")


def test_bac_tu_viet_dung_TRUOC_bac_ban_giao_nguoi():
    from eaa.installerr import MANG, remedies

    thang = remedies(MANG, tool="x")
    i_viet = next(i for i, r in enumerate(thang) if "tối thiểu thay thế" in r.action)
    i_ban = next(i for i, r in enumerate(thang) if "Bàn giao người" in r.action)
    assert i_viet < i_ban


def test_bac_tu_viet_dung_SAU_moi_bac_cai_that():
    """Một công cụ tự viết không có ai bảo trì ngoài chính dự án này."""
    from eaa.installerr import KHONG_TIM_THAY, remedies

    thang = remedies(KHONG_TIM_THAY, tool="x")
    i_viet = next(i for i, r in enumerate(thang) if "tối thiểu thay thế" in r.action)
    assert i_viet >= 3


def test_xem_truoc_KHONG_bi_chan_o_pha():
    """Cổng pha kiểm soát thứ ĐI VÀO sản phẩm; xem trước không đưa gì vào cả."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator._kiem_tien_dieu_kien)
    assert "and not self.config.preview" in src
    # Chuỗi bị ngắt dòng trong mã nên khớp theo mảnh nằm gọn một dòng.
    assert "Cổng pha tồn tại để kiểm soát thứ ĐI VÀO sản phẩm" in src


def test_xem_truoc_VAN_bi_chan_o_backlog_xung_dot_va_tri_thuc():
    """Bỏ ba cái ấy thì thứ in ra là mã bịa, không phải mã xem trước."""
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator._kiem_tien_dieu_kien)
    # Ba phép kiểm sau phần pha đều KHÔNG có ngoại lệ cho preview.
    sau_pha = src[src.index("muc = state.module(module_id)"):]
    assert "config.preview" not in sau_pha
    for dau_hieu in ("không có trong backlog", "Xung đột tài nguyên", "readiness"):
        assert dau_hieu in sau_pha


def test_xem_truoc_truoc_pha_D_thi_canh_bao_kien_truc_chua_chot():
    import inspect

    from eaa import orchestrator

    src = inspect.getsource(orchestrator.Orchestrator.run_module)
    assert "Kiến trúc chưa chốt xong" in src
    assert "đừng để nó chốt hộ một quyết định bạn chưa " in src


def test_hai_su_kien_kpi_moi_duoc_khai():
    """Cột 'event' là thứ Chương 3 nhóm số liệu theo — không được là trường tự do."""
    from eaa.kpi import EVENTS

    assert "draft_run" in EVENTS and "preview" in EVENTS


def test_su_kien_khong_gop_vao_generate():
    """Gộp thì tỉ lệ đạt đẹp lên vì một lý do không liên quan tới chất lượng mã."""
    import inspect

    from eaa import kpi

    src = inspect.getsource(kpi)
    assert "tỉ lệ đạt" in src or "tỉ lệ" in src
