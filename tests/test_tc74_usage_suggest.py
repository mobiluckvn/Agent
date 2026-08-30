"""TC-74 — đo công cụ sau khi dùng thật, và tự nhìn lại.

Hai bất biến:

* **Không cảnh báo sớm.** Hai lần hỏng đầu tiên có thể chỉ là hai lần đầu vào
  xấu, và một cảnh báo sai làm người ta thôi đọc cảnh báo.
* **Mọi đề nghị phải có SỐ đi kèm.** Một đề nghị không kèm bằng chứng đếm được
  là một ý kiến — và một agent đưa ý kiến về việc nên xây gì tiếp là một agent
  sớm muộn cũng đề nghị xây thứ nó thích.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.confidence import DA_KIEM, SUY_RA
from eaa.suggest import (
    LOAI_CACH_SUA_KEM,
    LOAI_CAU_HOI_QUA_LON,
    LOAI_CONG_CU,
    LOAI_KY_NANG,
    LOAI_SUA_CONG_CU,
    analyse,
)
from eaa.toolusage import (
    CHAM_MS,
    SO_LAN_DU_DE_KET_LUAN,
    TI_LE_DANG_LO,
    UsageLog,
)


# ═══════════════════════ nhật ký dùng công cụ ═══════════════════════


def test_ghi_va_gop_dung(tmp_path):
    n = UsageLog(tmp_path)
    n.record("gop_csv", ok=True, duration_ms=100)
    n.record("gop_csv", ok=False, duration_ms=50, error="ValueError: x")
    n.record("khac", ok=True)

    s = n.stats_for("gop_csv")
    assert (s.ok, s.failed, s.runs) == (1, 1, 2)
    assert s.avg_ms == 75
    assert "ValueError" in s.last_error


def test_mot_lan_dung_khong_nhay_len_100_phan_tram(tmp_path):
    n = UsageLog(tmp_path)
    n.record("x", ok=True)
    assert n.stats_for("x").success_rate < 1.0


def test_chua_du_so_lan_thi_KHONG_canh_bao(tmp_path):
    """Một cảnh báo sai làm người ta thôi đọc cảnh báo."""
    n = UsageLog(tmp_path)
    for _ in range(SO_LAN_DU_DE_KET_LUAN - 1):
        n.record("x", ok=False)
    s = n.stats_for("x")
    assert s.enough_data is False
    assert s.concerning is False
    assert n.concerning() == []


def test_du_so_lan_va_ti_le_thap_thi_canh_bao(tmp_path):
    n = UsageLog(tmp_path)
    for _ in range(SO_LAN_DU_DE_KET_LUAN):
        n.record("x", ok=False, error="hỏng")
    s = n.stats_for("x")
    assert s.enough_data is True and s.concerning is True
    assert s.success_rate < TI_LE_DANG_LO
    assert [c.tool for c in n.concerning()] == ["x"]


def test_cong_cu_tot_khong_bi_canh_bao(tmp_path):
    n = UsageLog(tmp_path)
    for _ in range(10):
        n.record("x", ok=True, duration_ms=10)
    assert n.concerning() == []


def test_cong_cu_cham_bi_danh_dau(tmp_path):
    n = UsageLog(tmp_path)
    for _ in range(SO_LAN_DU_DE_KET_LUAN):
        n.record("x", ok=True, duration_ms=CHAM_MS + 1000)
    s = n.stats_for("x")
    assert s.slow is True and s.concerning is False
    assert "CHẬM" in s.render()


def test_muc_tin_cay_theo_so_lan_do(tmp_path):
    n = UsageLog(tmp_path)
    n.record("x", ok=True)
    assert n.stats_for("x").confidence_level == SUY_RA
    for _ in range(SO_LAN_DU_DE_KET_LUAN):
        n.record("x", ok=True)
    assert n.stats_for("x").confidence_level == DA_KIEM


def test_chua_dung_lan_nao(tmp_path):
    assert UsageLog(tmp_path).stats_for("x").runs == 0
    assert "chưa dùng lần nào" in UsageLog(tmp_path).stats_for("x").render()


def test_dong_hong_khong_lam_sap(tmp_path):
    n = UsageLog(tmp_path)
    n.record("x", ok=True)
    with n.path.open("a", encoding="utf-8") as f:
        f.write("khong phai json\n")
    n.record("x", ok=True)
    assert n.stats_for("x").runs == 2


def test_toolforge_ghi_lai_moi_lan_goi(tmp_path):
    """Ghi cả lần đạt lẫn lần hỏng — chỉ ghi thành công là tự tin sai hướng."""
    from eaa.toolforge import DA_KIEM_THU, ForgedTool, ToolForge, ToolRegistry

    ma = ('MO_TA = "x"\nSCHEMA = {}\n\n\ndef run(**kw):\n'
          '    return str(1 // int(kw.get("chia", 1)))\n\n\ndef test_x():\n'
          '    assert run() == "1"\n')
    kho = ToolRegistry(tmp_path)
    kho.save(ForgedTool(name="chia", purpose="thử", code=ma, status=DA_KIEM_THU))
    kho.approve("chia", by="x")
    xuong = ToolForge(registry=kho)

    xuong.run("chia", {"chia": 1})
    with pytest.raises(Exception):
        xuong.run("chia", {"chia": 0})

    s = UsageLog(tmp_path).stats_for("chia")
    assert (s.ok, s.failed) == (1, 1)
    assert "ZeroDivisionError" in s.last_error


# ═══════════════════════════ tự nhìn lại ═══════════════════════════


def _nhat_ky(tmp_path, *luot) -> Path:
    p = tmp_path / "chat_log.jsonl"
    p.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in luot),
                 encoding="utf-8")
    return p


def _bi_tu_choi(*argv_list, hit_limit=False):
    return {"commands_run": [], "hit_limit": hit_limit,
            "steps": [{"argv": list(a.split()), "refused": "ngoài danh mục"}
                      for a in argv_list]}


def test_khong_co_tin_hieu_thi_noi_thang_la_khong_co(tmp_path):
    """Cám dỗ lớn nhất của một lệnh tên 'suggest' là luôn tìm ra điều gì đó."""
    bc = analyse(chat_log=_nhat_ky(tmp_path, {"commands_run": ["status"]}))
    assert bc.empty is True
    assert "Chưa thấy gì đáng làm" in bc.render()
    assert "không phải một thất bại" in bc.render()


def test_nhat_ky_chua_co_thi_khong_sap(tmp_path):
    assert analyse(chat_log=tmp_path / "khong-co.jsonl").empty is True


def test_lenh_ngoai_danh_muc_lap_lai_thi_de_nghi_viet_cong_cu(tmp_path):
    p = _nhat_ky(tmp_path, _bi_tu_choi("gop bao cao"), _bi_tu_choi("gop bao cao"))
    bc = analyse(chat_log=p)
    dn = [s for s in bc.suggestions if s.kind == LOAI_CONG_CU]
    assert len(dn) == 1
    assert dn[0].count == 2
    assert "2" in dn[0].evidence
    assert dn[0].action[:2] == ("tool", "propose")


def test_bi_chan_o_RANH_GIOI_QUYEN_khong_phai_khoang_trong_nang_luc(tmp_path):
    """Đề nghị 'viết công cụ' cho một gate bị chặn là đề nghị lách rào."""
    p = _nhat_ky(tmp_path, _bi_tu_choi("gate approve"), _bi_tu_choi("gate approve"),
                 _bi_tu_choi("flash"), _bi_tu_choi("flash"))
    bc = analyse(chat_log=p)

    assert not any(s.kind == LOAI_CONG_CU for s in bc.suggestions)
    ten = dict(bc.boundary_hits)
    assert ten.get("gate approve") == 2 and ten.get("flash") == 2
    ra = bc.render()
    assert "ĐÚNG như thiết kế" in ra
    assert "không nên có" in ra


def test_mot_lan_thi_chua_du_de_de_nghi(tmp_path):
    bc = analyse(chat_log=_nhat_ky(tmp_path, _bi_tu_choi("gop bao cao")))
    assert bc.empty is True


def test_chuoi_da_lap_thi_de_nghi_rut_ky_nang(tmp_path):
    from eaa.skills import mine

    p = _nhat_ky(tmp_path, *[{"commands_run": ["status", "plan list"]}] * 2)
    bc = analyse(chat_log=p, mined=mine(p))
    dn = [s for s in bc.suggestions if s.kind == LOAI_KY_NANG]
    assert dn and dn[0].count == 2
    assert dn[0].action[:2] == ("skill", "mine")


def test_nhieu_luot_cham_tran_thi_de_nghi_thu_gon(tmp_path):
    p = _nhat_ky(tmp_path, {"hit_limit": True}, {"hit_limit": True})
    bc = analyse(chat_log=p)
    assert any(s.kind == LOAI_CAU_HOI_QUA_LON for s in bc.suggestions)


def test_cong_cu_hay_hong_thi_de_nghi_xem_lai(tmp_path):
    n = UsageLog(tmp_path)
    for _ in range(SO_LAN_DU_DE_KET_LUAN):
        n.record("gop_csv", ok=False, error="ValueError")
    bc = analyse(chat_log=tmp_path / "khong-co.jsonl", usage_log=n)
    dn = [s for s in bc.suggestions if s.kind == LOAI_SUA_CONG_CU]
    assert dn and "gop_csv" in dn[0].subject
    assert "0/4 lần đạt" in dn[0].evidence


def test_cach_sua_hay_truot_thi_de_nghi_tra_lai(tmp_path):
    from eaa.playbook import Playbook

    so = Playbook(tmp_path)
    m = so.record("error: undefined reference to `x'", "cách A")
    so.mark(m.signature, worked=False)
    so.mark(m.signature, worked=False)

    bc = analyse(chat_log=tmp_path / "khong-co.jsonl", playbook=so)
    dn = [s for s in bc.suggestions if s.kind == LOAI_CACH_SUA_KEM]
    assert dn and "1 lần trúng / 2 lần trượt" in dn[0].evidence


def test_moi_de_nghi_deu_co_so_di_kem(tmp_path):
    from eaa.skills import mine

    p = _nhat_ky(tmp_path,
                 _bi_tu_choi("gop bao cao"), _bi_tu_choi("gop bao cao"),
                 {"commands_run": ["status", "plan list"]},
                 {"commands_run": ["status", "plan list"]})
    bc = analyse(chat_log=p, mined=mine(p))
    assert bc.suggestions
    for s in bc.suggestions:
        assert s.count >= 1
        assert any(ch.isdigit() for ch in s.evidence), s.evidence


def test_ban_in_nhac_lai_rang_moi_de_nghi_van_qua_cong(tmp_path):
    p = _nhat_ky(tmp_path, _bi_tu_choi("gop bao cao"), _bi_tu_choi("gop bao cao"))
    assert "vẫn đi qua đủ cổng" in analyse(chat_log=p).render()


def test_dem_dung_so_luot_da_doc(tmp_path):
    p = _nhat_ky(tmp_path, {"commands_run": []}, {"commands_run": []},
                 {"commands_run": []})
    assert analyse(chat_log=p).turns_read == 3
