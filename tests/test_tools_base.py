"""Báo cáo chuẩn hóa của Tool Layer — nền của bất biến merge (SDD §4, NFR-01).

Bất biến "merge chỉ khi TOÀN BỘ ToolReport.passed" chỉ vững nếu bản thân
``passed`` không nói dối được. Đây là chỗ canh điều đó.
"""

from __future__ import annotations

import pytest

from eaa.tools.base import CodeArtifact, Severity, ToolError, ToolGate, ToolReport


def test_bao_cao_dat_ma_van_co_loi_muc_error_bi_tu_choi() -> None:
    with pytest.raises(ValueError, match="tự mâu thuẫn"):
        ToolReport(
            gate="compile",
            passed=True,
            errors=[ToolError("thiếu dấu chấm phẩy", file="a.c", line=12)],
        )


def test_bao_cao_dat_van_duoc_mang_canh_bao() -> None:
    """Cảnh báo không chặn cổng — người phân loại mức nghiêm trọng (công đoạn E1)."""
    bao_cao = ToolReport(
        gate="static",
        passed=True,
        warnings=[ToolError("biến che khuất", severity=Severity.WARNING)],
        metrics={"flash_pct": 31.2},
    )
    assert bao_cao.passed
    assert "ĐẠT" in bao_cao.summary


def test_bao_cao_khong_dat_giu_nguyen_loi_de_dua_vao_vong_tu_sua() -> None:
    bao_cao = ToolReport(
        gate="compile",
        passed=False,
        errors=[ToolError("khai báo ngầm", file="drv.c", line=42, rule_id="C0103")],
        duration_s=1.5,
    )
    assert not bao_cao.passed
    assert str(bao_cao.errors[0]) == "drv.c:42: [C0103] khai báo ngầm"
    assert "KHÔNG ĐẠT" in bao_cao.summary


def test_loi_khong_co_vi_tri_van_in_duoc() -> None:
    assert str(ToolError("hết bộ nhớ")) == "hết bộ nhớ"
    assert str(ToolError("lỗi tệp", file="a.c")) == "a.c: lỗi tệp"


def test_artifact_mang_du_truong_truy_vet_NFR07() -> None:
    artifact = CodeArtifact(
        files={"src/drv.c": "int main(void){return 0;}"},
        prompt_hash="sha256:deadbeef",
        model="mock-deterministic-1",
        constraints_version="sha256:ab12",
        chunk_ids=["#ds-012"],
    )
    for truong in ("prompt_hash", "model", "constraints_version", "chunk_ids"):
        assert getattr(artifact, truong), f"thiếu trường truy vết {truong}"


def test_cong_kiem_chung_tuan_thu_giao_dien_ToolGate() -> None:
    class CongGia:
        name = "gia"

        def run(self, artifact: CodeArtifact) -> ToolReport:
            return ToolReport(gate=self.name, passed=True)

    assert isinstance(CongGia(), ToolGate)
