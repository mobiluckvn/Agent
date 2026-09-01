"""TC-04, TC-05, TC-16, TC-21, TC-19 — Prompt Composer và bảy kỹ thuật nén.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-04 | Ràng buộc có mặt trong 100% prompt | mọi nhánh lắp ráp, kể cả vòng vá |
| TC-05 | Datasheet Injection đúng chunk | chunk bus có mặt, chunk bộ đếm không |
| TC-16 | Vượt ngân sách bị chặn trước khi gọi API | và báo đích danh lớp vượt |
| TC-21 | Interface-only (K3) | thân module đã merge không bao giờ được gửi lại |
| TC-19 | Vòng tự sửa dạng vá | prompt sửa không chứa toàn văn tệp |

TC-04 là test dễ bị hiểu nhầm là hình thức. Nó không hình thức: toàn bộ lập
luận chống Context Loss của đề án (ADR-02, NT3) dựa trên việc ràng buộc được
NẠP LẠI ở mọi lần gọi thay vì được "nhớ" từ lượt trước. Chỉ cần một nhánh lắp
ráp bỏ sót lớp đó là lập luận sụp — và nhánh dễ bỏ sót nhất chính là vòng tự
sửa, nơi người ta hay nghĩ "chỉ gửi lỗi thôi cho gọn".
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from eaa.composer import ComposerConfig, ComposerError, PromptComposer, Task, extract_function
from eaa.graph import KnowledgeGraph
from eaa.kb import KnowledgeBase
from eaa.ledger import ErrorLedger
from eaa.llm.base import BudgetExceeded
from eaa.llm.mock import MockLLM
from eaa.tools.base import ToolError, ToolReport

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    """Bản sao dự án mẫu, kèm một module đã merge để thử lớp interface."""
    dich = tmp_path / "robot_balance"
    dich.mkdir()
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        (dich / ten).write_text(
            (DU_AN_MAU / ten).read_text(encoding="utf-8"), encoding="utf-8"
        )
    ds = dich / "datasheets"
    ds.mkdir()
    for path in (DU_AN_MAU / "datasheets").glob("*.md"):
        (ds / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    # Module đã merge: có CẢ tệp tiêu đề và tệp mã nguồn. Có mặt tệp .c là điều
    # kiện để TC-21 có ý nghĩa — phải chứng minh nó KHÔNG bị gửi đi.
    src = dich / "firmware" / "src"
    src.mkdir(parents=True)
    (src / "hal_bus.h").write_text(
        textwrap.dedent(
            """\
            // Lớp truy cập bus nối tiếp: khởi tạo, đọc, ghi.
            #ifndef HAL_BUS_H
            #define HAL_BUS_H
            #include <stdint.h>
            void hal_bus_init(uint32_t clock_hz);
            uint8_t hal_bus_read(uint8_t addr, uint8_t reg);
            #endif
            """
        ),
        encoding="utf-8",
    )
    (src / "hal_bus.c").write_text(
        textwrap.dedent(
            """\
            #include "hal_bus.h"
            void hal_bus_init(uint32_t clock_hz)
            {
                CHUOI_THAN_HAM_KHONG_DUOC_XUAT_HIEN_TRONG_PROMPT;
            }
            uint8_t hal_bus_read(uint8_t addr, uint8_t reg)
            {
                return 0u;
            }
            """
        ),
        encoding="utf-8",
    )
    return dich


@pytest.fixture()
def composer(du_an: Path, tmp_path: Path) -> PromptComposer:
    kb = KnowledgeBase.load(du_an)
    graph = KnowledgeGraph.build(kb.hardware, kb.datasheets)
    ledger = ErrorLedger(tmp_path / "error_ledger.jsonl")
    return PromptComposer(kb, graph, ledger)


NHIEM_VU_BUS = Task(
    module_id="drv_bus_sensor",
    goal="Đọc số đo cảm biến qua bus nối tiếp, chu kỳ 10 ms.",
    acceptance=("Kiểm mã trạng thái sau mỗi thao tác bus.", "Không dùng số thực."),
    uses=("twi", "imu"),
    output_files=("src/drv_bus_sensor.c", "src/drv_bus_sensor.h"),
)


# --------------------------------------------------------------------------
# TC-04 — ràng buộc có mặt trong 100% lần gọi
# --------------------------------------------------------------------------


def test_tc04_rang_buoc_co_mat_trong_prompt_sinh_ma(composer: PromptComposer) -> None:
    prompt = composer.build(NHIEM_VU_BUS)
    toan_van = prompt.full_text()

    for cam in composer.kb.constraints.forbidden:
        assert f"CẤM {cam}" in toan_van, f"thiếu ràng buộc cấm {cam!r}"
    for ten, gia_tri in composer.kb.constraints.limits.items():
        assert ten in toan_van and str(gia_tri) in toan_van


def test_tc04_rang_buoc_van_co_mat_trong_prompt_vong_tu_sua(
    composer: PromptComposer,
) -> None:
    """Nhánh dễ bỏ sót nhất: "chỉ gửi lỗi thôi cho gọn"."""
    bao_cao = ToolReport(
        gate="compile", passed=False, errors=[ToolError("lỗi", file="src/a.c", line=3)]
    )
    prompt = composer.build_repair(
        NHIEM_VU_BUS, None, bao_cao, {"src/a.c": "void f(void)\n{\n    x;\n}\n"}
    )
    assert "CẤM delay()" in prompt.full_text()
    assert "RÀNG BUỘC CỨNG" in prompt.system_instruction


def test_tc04_rang_buoc_nam_trong_system_instruction(composer: PromptComposer) -> None:
    """AIS §2: Gemini tách system instruction khỏi nội dung — tận dụng để ràng
    buộc không bị trôi."""
    prompt = composer.build(NHIEM_VU_BUS)
    assert "CẤM malloc/new" in prompt.system_instruction


def test_tc04_bam_prompt_doi_khi_rang_buoc_doi(composer: PromptComposer, du_an: Path) -> None:
    """Truy vết NFR-07: đổi ràng buộc thì prompt phải khác, không được trùng băm."""
    truoc = composer.build(NHIEM_VU_BUS)

    path = du_an / "constraints.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("flash_pct_max: 50", "flash_pct_max: 40"),
        encoding="utf-8",
    )
    kb = KnowledgeBase.load(du_an)
    moi = PromptComposer(kb, KnowledgeGraph.build(kb.hardware, kb.datasheets)).build(
        NHIEM_VU_BUS
    )

    assert moi.hash != truoc.hash
    assert moi.constraints_version != truoc.constraints_version


def test_du_an_khong_co_rang_buoc_nao_thi_khong_duoc_sinh_ma(
    composer: PromptComposer,
) -> None:
    """Hard Constraints Spec là sản phẩm A1 và là đầu vào bắt buộc của mọi prompt."""
    composer.kb.constraints.raw.clear()
    with pytest.raises(ComposerError, match="công đoạn A1"):
        composer.build(NHIEM_VU_BUS)


def test_lop_rang_buoc_bi_cat_xen_thi_bi_bat(composer: PromptComposer) -> None:
    """Phép kiểm phải đối chiếu từng mục, không chỉ hỏi 'lớp này có chữ không'."""
    composer._lop_vai_tro = lambda: "## RÀNG BUỘC CỨNG (bắt buộc, không thương lượng)"
    with pytest.raises(ComposerError, match="delay\\(\\)"):
        composer.build(NHIEM_VU_BUS)


# --------------------------------------------------------------------------
# TC-05 — Datasheet Injection đúng chunk
# --------------------------------------------------------------------------


def test_tc05_prompt_chua_chunk_bus_khong_chua_chunk_bo_dem(
    composer: PromptComposer,
) -> None:
    prompt = composer.build(NHIEM_VU_BUS)
    toan_van = prompt.full_text()

    assert "ds-021" in toan_van and "TWBR" in toan_van
    assert "ds-022" in toan_van
    assert "ds-012" not in toan_van, "chunk bộ đếm không liên quan đã lọt vào prompt"
    assert "TCCR1A" not in toan_van
    assert prompt.chunk_ids and "ds-012" not in prompt.chunk_ids


def test_tc05_chunk_chua_duyet_G2_khong_bao_gio_vao_prompt(
    composer: PromptComposer,
) -> None:
    prompt = composer.build(Task(module_id="drv_imu", uses=("imu",)))
    assert "ds-032" not in prompt.full_text()
    assert "ACCEL_XOUT_H" not in prompt.full_text()


def test_chunk_kem_theo_cau_trich_dan_de_mo_hinh_dung_dung(
    composer: PromptComposer,
) -> None:
    """FR-RAG-02: mã phải mang '// ref: <chunk id>' — prompt phải đưa sẵn mẫu."""
    toan_van = composer.build(NHIEM_VU_BUS).full_text()
    assert "// ref: ds-021" in toan_van


def test_khong_co_chunk_thi_prompt_noi_thang_la_thieu(composer: PromptComposer) -> None:
    """Cấm đoán giá trị thanh ghi để lấp chỗ trống (FR-GAP-03)."""
    prompt = composer.build(Task(module_id="pid_controller"))
    assert "KHÔNG được đoán" in prompt.full_text()
    assert prompt.chunk_ids == ()


# --------------------------------------------------------------------------
# TC-21 — Interface-only (K3)
# --------------------------------------------------------------------------


def test_tc21_prompt_chi_chua_header_khong_chua_than_module_da_merge(
    composer: PromptComposer,
) -> None:
    nhiem_vu = Task(
        module_id="drv_bus_sensor", uses=("twi", "imu"), depends_on=("hal_bus",)
    )
    toan_van = composer.build(nhiem_vu).full_text()

    assert "hal_bus_init" in toan_van, "khai báo hàm của module phụ thuộc phải có"
    assert "uint8_t hal_bus_read" in toan_van
    assert "CHUOI_THAN_HAM_KHONG_DUOC_XUAT_HIEN_TRONG_PROMPT" not in toan_van
    assert "hal_bus.c" not in toan_van


def test_tc21_kem_mot_dong_tom_tat_chuc_nang(composer: PromptComposer) -> None:
    """K3: tệp tiêu đề + 1 dòng tóm tắt, không phải tệp tiêu đề trần."""
    toan_van = composer.build(
        Task(module_id="drv_bus_sensor", depends_on=("hal_bus",))
    ).full_text()
    assert "Lớp truy cập bus nối tiếp" in toan_van


def test_module_phu_thuoc_chua_co_header_thi_noi_ro(composer: PromptComposer) -> None:
    toan_van = composer.build(
        Task(module_id="x", depends_on=("module_chua_ton_tai",))
    ).full_text()
    assert "chưa có tệp tiêu đề" in toan_van


def test_lop_interface_lo_chua_tep_ma_nguon_bi_chan(composer: PromptComposer) -> None:
    """Rào an toàn cho FR-CTX-02, phòng khi có ai đổi cách dựng lớp này."""
    goc = composer._lop_interface
    composer._lop_interface = lambda task, **kw: "```file:src/hal_bus.c\nvoid f(void){}\n```"
    try:
        with pytest.raises(ComposerError, match="FR-CTX-02"):
            composer.build(Task(module_id="x", depends_on=("hal_bus",)))
    finally:
        composer._lop_interface = goc


# --------------------------------------------------------------------------
# TC-16 — ngân sách ngữ cảnh
# --------------------------------------------------------------------------


def test_prompt_binh_thuong_nam_trong_ngan_sach(composer: PromptComposer) -> None:
    prompt = composer.build(NHIEM_VU_BUS)
    prompt.check_budget()
    assert prompt.total_tokens() <= 8_000


def test_tc16_ep_nhieu_chunk_lam_vuot_ngan_sach_thi_bi_chan(
    composer: PromptComposer,
) -> None:
    composer.config = ComposerConfig(top_k_chunks=3, layer_budgets={"datasheet_chunks": 20})
    with pytest.raises(BudgetExceeded, match="datasheet_chunks"):
        composer.build(NHIEM_VU_BUS)


def test_tc16_vuot_ngan_sach_thi_khong_co_loi_goi_mo_hinh_nao(
    composer: PromptComposer,
) -> None:
    """Điểm cốt lõi của TC-16: chặn TRƯỚC khi gọi API, không phải sau."""
    llm = MockLLM()
    composer.config = ComposerConfig(layer_budgets={"task": 5})
    with pytest.raises(BudgetExceeded):
        prompt = composer.build(NHIEM_VU_BUS, counter=llm.count_tokens)
        llm.generate(prompt)
    assert llm.call_count == 0


def test_luoc_quy_tac_loi_truoc_khi_tuyen_bo_vuot_ngan_sach(
    composer: PromptComposer,
) -> None:
    """Nhường chỗ theo thứ tự ưu tiên, và ghi lại đã nhường cái gì.

    Bài này phải làm TRẦN TỔNG chật thì mới đúng đề. Trước SL-136 nó dựng cảnh
    chật bằng cách cho quy tắc lỗi dài quá PHẦN CỦA LỚP — nhưng lúc ấy lớp quy
    tắc chưa biết tự nhét vừa, nên "vượt phần của lớp" và "hết chỗ thật" trông
    giống nhau. Nay lớp quy tắc tự nhét vừa 300 token của nó, nên muốn kiểm
    việc NHƯỜNG CHỖ thì phải để nó cạnh tranh với một trần tổng thật sự chật.
    """
    for i in range(5):
        composer.ledger.add(
            module="drv_bus_sensor",
            category="other",
            description=f"lỗi {i}",
            rule="quy tắc rất dài " * 60,
        )
    # Trần tổng chỉ vừa đủ cho vai trò + chunk + nhiệm vụ: quy tắc lỗi phải là
    # thứ nhường chỗ đầu tiên.
    goc = composer.config
    composer.config = ComposerConfig(budget=goc.budget, layer_budgets=goc.layer_budgets)
    truoc = composer.build(NHIEM_VU_BUS)
    composer.config = ComposerConfig(
        budget=truoc.total_tokens() - 100, layer_budgets=goc.layer_budgets
    )

    prompt = composer.build(NHIEM_VU_BUS)

    assert "error_rules" in prompt.trimmed
    assert prompt.layer("error_rules") is None
    assert "TWBR" in prompt.full_text(), "chunk tài liệu KHÔNG được lược cùng"


def test_quy_tac_loi_TU_NHET_VUA_thay_vi_bi_xoa_ca_lop(
    composer: PromptComposer,
) -> None:
    """SL-136 — còn chỗ trong trần tổng thì không được vứt cả lớp quy tắc.

    Lý do người viết lúc từ chối gate đi qua đúng lớp này. Vứt cả lớp vì nó dài
    hơn phần của nó, trong khi trần tổng còn thừa quá nửa, là ném đi tín hiệu
    riêng biệt nhất về đúng module đang sinh.
    """
    for i in range(5):
        composer.ledger.add(
            module="drv_bus_sensor",
            category="other",
            description=f"lỗi {i}",
            rule=f"KHÔNG lặp lại lỗi {i}: " + "quy tắc rất dài " * 60,
        )
    prompt = composer.build(NHIEM_VU_BUS)

    assert "error_rules" not in prompt.trimmed, "vẫn xóa cả lớp dù trần tổng còn thừa"
    lop = prompt.layer("error_rules")
    assert lop is not None and lop.content.strip(), "lớp quy tắc lỗi rỗng"
    assert prompt.total_tokens() <= prompt.budget


def test_chunk_tai_lieu_khong_bao_gio_bi_luoc_am_tham(composer: PromptComposer) -> None:
    """Lược một chunk = để mô hình cấu hình thanh ghi không có tài liệu."""
    composer.config = ComposerConfig(layer_budgets={"datasheet_chunks": 10}, budget=200)
    with pytest.raises(BudgetExceeded):
        composer.build(NHIEM_VU_BUS)


# --------------------------------------------------------------------------
# TC-19 — vòng tự sửa dạng vá
# --------------------------------------------------------------------------


NGUON_200_DONG = (
    "#include \"m.h\"\n\n"
    + "\n".join(f"// dòng đệm {i}" for i in range(80))
    + "\n\nvoid ham_khong_loi(void)\n{\n    int a = 1;\n}\n\n"
    "void ham_co_loi(uint8_t x)\n{\n"
    "    uint8_t y = x\n"           # dòng lỗi: thiếu dấu chấm phẩy
    "    (void)y;\n}\n\n"
    + "\n".join(f"// dòng đệm cuối {i}" for i in range(80))
    + "\n"
)
DONG_LOI = NGUON_200_DONG.splitlines().index("    uint8_t y = x") + 1


def test_tc19_prompt_sua_khong_chua_toan_van_tep(composer: PromptComposer) -> None:
    bao_cao = ToolReport(
        gate="compile",
        passed=False,
        errors=[ToolError("thiếu dấu chấm phẩy", file="src/m.c", line=DONG_LOI)],
    )
    prompt = composer.build_repair(
        NHIEM_VU_BUS, None, bao_cao, {"src/m.c": NGUON_200_DONG}
    )
    toan_van = prompt.full_text()

    assert "ham_co_loi" in toan_van, "hàm chứa lỗi phải có mặt"
    assert "thiếu dấu chấm phẩy" in toan_van, "thông báo lỗi phải có mặt"
    assert "ham_khong_loi" not in toan_van, "hàm không liên quan đã bị gửi kèm"
    assert "dòng đệm 40" not in toan_van
    assert toan_van.count("dòng đệm") == 0


def test_tc19_yeu_cau_tra_ve_ban_va_chu_khong_phai_ca_tep(
    composer: PromptComposer,
) -> None:
    bao_cao = ToolReport(
        gate="static",
        passed=False,
        errors=[ToolError("vi phạm", file="src/m.c", line=DONG_LOI)],
    )
    toan_van = composer.build_repair(
        NHIEM_VU_BUS, None, bao_cao, {"src/m.c": NGUON_200_DONG}
    ).full_text()

    assert "KHÔNG viết lại toàn bộ tệp" in toan_van
    assert "sửa chỗ này" in toan_van


def test_prompt_sua_bo_lop_nhiem_vu_goc(composer: PromptComposer) -> None:
    """Vòng vá không lặp lại nhiệm vụ ban đầu — đó là phần nén ~70% của §3.2."""
    bao_cao = ToolReport(gate="compile", passed=False, errors=[ToolError("x")])
    prompt = composer.build_repair(NHIEM_VU_BUS, None, bao_cao, {})
    assert prompt.layer("task") is None
    assert prompt.layer("repair") is not None


def test_khong_dinh_vi_duoc_ham_loi_thi_noi_ro_thay_vi_gui_ca_tep(
    composer: PromptComposer,
) -> None:
    bao_cao = ToolReport(gate="compile", passed=False, errors=[ToolError("lỗi chung chung")])
    toan_van = composer.build_repair(
        NHIEM_VU_BUS, None, bao_cao, {"src/m.c": NGUON_200_DONG}
    ).full_text()
    assert "không định vị được hàm" in toan_van
    assert "dòng đệm" not in toan_van


# --------------------------------------------------------------------------
# Trích hàm chứa dòng lỗi
# --------------------------------------------------------------------------


def test_trich_dung_ham_chua_dong_loi() -> None:
    doan = extract_function(NGUON_200_DONG, DONG_LOI)
    assert doan.startswith("void ham_co_loi(uint8_t x)")
    assert doan.rstrip().endswith("}")
    assert "ham_khong_loi" not in doan


def test_trich_ham_dau_tien_va_ham_cuoi_cung() -> None:
    nguon = "void a(void)\n{\n    int x;\n}\n\nvoid b(void)\n{\n    int y;\n}\n"
    assert "void a" in extract_function(nguon, 3)
    assert "void b" in extract_function(nguon, 7)
    assert "void a" not in extract_function(nguon, 7)


def test_khong_tim_duoc_bien_ham_thi_tra_cua_so_va_noi_ro() -> None:
    doan = extract_function("int x;\nint y;\nint z;\n", 2)
    assert "không xác định được biên hàm" in doan
    assert "int y;" in doan


def test_trich_ham_tren_nguon_rong() -> None:
    assert extract_function("", 1) == ""


def test_so_dong_ngoai_pham_vi_khong_no() -> None:
    extract_function("int x;\n", 999)


# --------------------------------------------------------------------------
# K5 và K6 trong prompt
# --------------------------------------------------------------------------


def test_tc10_quy_tac_tu_error_ledger_vao_prompt_lan_sau(
    composer: PromptComposer,
) -> None:
    """Nửa sau của TC-10: lỗi đã ghi trở thành ví dụ phủ định."""
    composer.ledger.add(
        module="drv_bus_sensor",
        category="hallucinated_register",
        description="Mô hình dùng một thanh ghi không tồn tại trên thiết bị đích",
        rule="KHÔNG dùng REG_KHONG_CO — thiết bị đích không có thanh ghi này",
    )
    toan_van = composer.build(NHIEM_VU_BUS).full_text()

    assert "TUYỆT ĐỐI TRÁNH LẶP LẠI" in toan_van
    assert "KHÔNG dùng REG_KHONG_CO" in toan_van


def test_nhat_ky_rong_thi_khong_co_lop_quy_tac_loi(composer: PromptComposer) -> None:
    assert composer.build(NHIEM_VU_BUS).layer("error_rules") is None


def test_k6_su_kien_phan_cung_thay_cho_ca_ho_so(composer: PromptComposer) -> None:
    toan_van = composer.build(NHIEM_VU_BUS).full_text()
    assert "PHẦN CỨNG LIÊN QUAN" in toan_van
    assert "TWBR" in toan_van
    assert "mechanics" not in toan_van, "không gửi cả hồ sơ phần cứng"
    assert "friction_coeff" not in toan_van


def test_k6_canh_bao_xung_dot_di_thang_vao_prompt(composer: PromptComposer) -> None:
    composer.graph.add_module("kernel_tick", uses=["timer1"])
    toan_van = composer.build(Task(module_id="drv_stepper", uses=("timer1",))).full_text()
    assert "XUNG ĐỘT" in toan_van


def test_k4_chi_gui_trang_thai_lien_quan_khong_gui_ca_backlog(
    composer: PromptComposer, du_an: Path
) -> None:
    from eaa.state import BacklogItem, ProjectState

    state = ProjectState(
        phase="D",
        backlog=[
            BacklogItem(id="drv_bus_sensor", status="in_verify", retries=2),
            BacklogItem(id="hal_bus", status="merged"),
            BacklogItem(id="module_khong_lien_quan", status="todo"),
        ],
    )
    toan_van = composer.build(
        Task(module_id="drv_bus_sensor", uses=("twi",), depends_on=("hal_bus",)), state
    ).full_text()

    assert "in_verify" in toan_van and "2" in toan_van
    assert "hal_bus" in toan_van
    assert "module_khong_lien_quan" not in toan_van


# --------------------------------------------------------------------------
# Prompt lắp xong dùng được thật
# --------------------------------------------------------------------------


def test_prompt_lap_xong_goi_duoc_mock_va_sinh_ra_ma(composer: PromptComposer) -> None:
    llm = MockLLM()
    prompt = composer.build(NHIEM_VU_BUS, counter=llm.count_tokens)
    artifact = llm.generate(prompt)

    assert artifact.files
    assert artifact.constraints_version == composer.kb.constraints.content_version
    assert artifact.chunk_ids == list(prompt.chunk_ids)
    assert artifact.prompt_hash == prompt.hash


def test_lap_prompt_hai_lan_cho_ket_qua_giong_het(composer: PromptComposer) -> None:
    """Điều kiện để thực nghiệm A/B của Chương 3 tái lập được."""
    assert composer.build(NHIEM_VU_BUS).hash == composer.build(NHIEM_VU_BUS).hash


def test_dinh_dang_tra_loi_duoc_neu_ro_trong_prompt(composer: PromptComposer) -> None:
    assert "```file:" in composer.build(NHIEM_VU_BUS).full_text()
