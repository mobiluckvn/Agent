"""Adapter mô hình nền — Google Gemini.

EAA-AIS-05 §2 (cấu hình mô hình), EAA-SDD-03 §6 (giao tiếp LLM và xử lý lỗi),
EAA-SRS-01 NFR-06, FR-LLM-01; TC-11, TC-14.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-18.

Gọi thẳng REST bằng thư viện chuẩn, KHÔNG thêm phụ thuộc mới. Lý do không dùng
SDK của nhà cung cấp: NFR-04 chốt sản phẩm chỉ phụ thuộc Python, toolchain và
Git; và một SDK lên phiên bản giữa kỳ thực nghiệm là thêm một biến nữa có thể
làm hỏng so sánh A/B, đúng loại rủi ro R1 mà EAA-STP-04 đã lường. Phần REST
được dùng ở đây hẹp và ổn định: sinh nội dung, và đếm token.

Bốn kỷ luật của adapter này:

* **Ghim phiên bản mô hình.** Không dùng bí danh kiểu "latest" — mô hình trôi
  phiên bản phá hỏng so sánh A/B y như toolchain trôi phiên bản (rủi ro R1).
* **Khóa chỉ từ biến môi trường** ``EAA_LLM_KEY``, và bị che trong mọi đầu ra:
  thông báo lỗi, nhật ký, và cả phần thân yêu cầu khi gỡ rối (NFR-06, TC-14).
* **Ngân sách kiểm TRƯỚC khi gọi**, bằng bộ đếm của chính mô hình sẽ gọi
  (FR-CTX-01). Vượt là lỗi lắp ráp, không phải chuyện cứ gửi thử.
* **Mỗi lời gọi được ghi lại** (prompt hash → phản hồi) làm bằng chứng tái lập
  — giảm thiểu rủi ro "mô hình đổi hành vi giữa kỳ thực nghiệm" (AIS §12).

Về mã phiên bản mô hình: giá trị mặc định dưới đây lấy từ EAA-AIS-05 §2. Mã
model của nhà cung cấp thay đổi theo thời gian, nên nó là **cấu hình**, không
phải hằng số trong mã: đặt trong Project State (``eaa init --model ...``). Nếu
nhà cung cấp trả 404, adapter nói thẳng rằng mã model không tồn tại và chỉ
sang lệnh liệt kê model, thay vì báo một lỗi mạng chung chung.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Sequence

from eaa.llm.base import (
    LLMError,
    LLMTimeout,
    Prompt,
    estimate_tokens,
    mask_secrets,
    parse_file_blocks,
)
from eaa.tools.base import CodeArtifact

__all__ = ["GeminiClient", "GeminiError", "ModelNotFound", "MissingApiKey", "API_KEY_ENV"]

#: Biến môi trường duy nhất chứa khóa — NFR-06. Không đọc từ tệp cấu hình, và
#: không nhận qua tham số dòng lệnh: một khóa truyền qua tham số sẽ nằm lại
#: trong lịch sử lệnh của shell.
API_KEY_ENV = "EAA_LLM_KEY"

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

#: Mã model mặc định theo EAA-AIS-05 §2. Ghi đè bằng ``eaa init --model``.
DEFAULT_MODEL = "gemini-3.1-pro-preview"


def _urllib_get(url: str, api_key: str, timeout: float) -> dict[str, Any]:
    """GET siêu dữ liệu model — dùng để biết trần token thật của model."""
    yeu_cau = urllib.request.Request(url, headers={"x-goog-api-key": api_key})
    with urllib.request.urlopen(yeu_cau, timeout=timeout) as phan_hoi:
        return json.loads(phan_hoi.read().decode("utf-8"))


def _urllib_transport(url: str, body: bytes, api_key: str, timeout: float) -> dict[str, Any]:
    """Lớp vận chuyển mặc định — thư viện chuẩn, không phụ thuộc mới.

    Khóa đi trong tiêu đề chứ không trong chuỗi truy vấn: chuỗi truy vấn nằm
    lại trong log của mọi proxy trên đường đi (NFR-06).
    """
    yeu_cau = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(yeu_cau, timeout=timeout) as phan_hoi:
        return json.loads(phan_hoi.read().decode("utf-8"))


class GeminiError(LLMError):
    """Lỗi khi gọi mô hình."""


class MissingApiKey(GeminiError):
    """Chưa cấu hình khóa API."""


class ModelNotFound(GeminiError):
    """Nhà cung cấp không có mã model này."""


@dataclass
class GeminiClient:
    """Adapter Gemini, tuân giao diện ``LLMClient`` của ``eaa/llm/base.py``."""

    provider: str = "gemini"
    model: str = DEFAULT_MODEL
    #: AIS §2: 0.2 cho sinh mã, 0.4 cho phân tích tinh chỉnh tại G4.
    temperature: float = 0.2
    #: Đặt cao để không bao giờ cắt cụt phản hồi; kỷ luật "module ≤ N dòng"
    #: được cưỡng chế ở cổng phân tích tĩnh, không dựa vào trần token (AIS §2).
    max_output_tokens: int = 200_000
    #: EAA-SDD-03 §6 chốt 120s. Đo thực tế ở Sprint 4: model Pro lớp suy luận
    #: sinh một module ~250 dòng có lúc vượt 120s, và một lần quá hạn làm hỏng
    #: cả lượt chạy vốn sắp xong. Nới lên 300s và cho cấu hình qua biến môi
    #: trường — trần này là tham số vận hành, không phải một khẳng định thiết kế.
    timeout_s: float = float(os.environ.get("EAA_LLM_TIMEOUT_S", "300"))
    #: SDD §6: retry 2 lần với backoff khi lỗi mạng.
    max_retries: int = 2
    backoff_s: float = 2.0
    #: Nhật ký lời gọi; ``None`` thì không ghi.
    call_log: Any = None
    #: Cho phép tiêm hàm gọi HTTP trong kiểm thử. Mặc định dùng urllib.
    transport: Any = None
    base_url: str = _BASE_URL
    #: Cho phép tiêm hàm GET siêu dữ liệu model trong kiểm thử.
    metadata_transport: Any = None

    _api_key: str = field(default="", init=False, repr=False)
    _tran_ra: int | None = field(default=None, init=False, repr=False)

    # ----------------------------------------------------------------------
    # Khóa API
    # ----------------------------------------------------------------------

    @property
    def api_key(self) -> str:
        if not self._api_key:
            khoa = os.environ.get(API_KEY_ENV, "").strip()
            if not khoa:
                raise MissingApiKey(
                    f"Chưa có khóa API trong biến môi trường {API_KEY_ENV}. "
                    "Khóa chỉ được đọc từ biến môi trường và không bao giờ ghi ra "
                    "log hay commit (NFR-06).\n"
                    f"    export {API_KEY_ENV}='<khóa của bạn>'"
                )
            self._api_key = khoa
        return self._api_key

    def __repr__(self) -> str:
        """Không bao giờ để khóa lọt vào biểu diễn của đối tượng.

        ``repr`` xuất hiện trong vết ngăn xếp, trong đầu ra của bộ gỡ rối và
        trong thông báo lỗi của pytest — ba nơi mà người ta hay dán nguyên vào
        báo cáo lỗi.
        """
        return (
            f"GeminiClient(provider={self.provider!r}, model={self.model!r}, "
            f"temperature={self.temperature}, api_key=***)"
        )

    # ----------------------------------------------------------------------
    # Gọi REST
    # ----------------------------------------------------------------------

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Gửi một yêu cầu, có retry và backoff theo EAA-SDD-03 §6.

        Lớp vận chuyển được gọi BÊN TRONG khối xử lý lỗi, không phải trước nó.
        Đặt khe tiêm ra ngoài thì mọi nhánh xử lý lỗi — 404, 403, 429, mất mạng,
        quá hạn — sẽ không có cách nào kiểm được, và chúng là những nhánh sẽ
        chạy vào đúng lúc tệ nhất.
        """
        url = f"{self.base_url}/models/{self.model}:{endpoint}"
        than = json.dumps(payload).encode("utf-8")
        gui = self.transport or _urllib_transport

        loi_cuoi: Exception | None = None
        for lan in range(self.max_retries + 1):
            try:
                return gui(url, than, self.api_key, self.timeout_s)
            except urllib.error.HTTPError as exc:
                chi_tiet = self._doc_loi(exc)
                if exc.code == 404:
                    raise ModelNotFound(
                        f"Nhà cung cấp không có mã model {self.model!r}. Mã model "
                        "thay đổi theo thời gian nên nó là CẤU HÌNH, không phải "
                        "hằng số: đặt lại bằng 'eaa init --model <mã>' sau khi tra "
                        "danh sách model hiện hành của nhà cung cấp.\n"
                        f"Chi tiết: {chi_tiet}"
                    ) from None
                if exc.code in (401, 403):
                    raise GeminiError(
                        f"Khóa API bị từ chối (HTTP {exc.code}). Kiểm tra "
                        f"{API_KEY_ENV} và quyền của khóa.\nChi tiết: {chi_tiet}"
                    ) from None
                if exc.code == 429 or 500 <= exc.code < 600:
                    # Lỗi tạm thời — thử lại có backoff (SDD §6).
                    loi_cuoi = GeminiError(f"HTTP {exc.code}: {chi_tiet}")
                    if lan < self.max_retries:
                        time.sleep(self.backoff_s * (2**lan))
                        continue
                    raise loi_cuoi from None
                raise GeminiError(f"HTTP {exc.code}: {chi_tiet}") from None
            except urllib.error.URLError as exc:
                loi_cuoi = GeminiError(f"Lỗi mạng: {mask_secrets(str(exc.reason))}")
                if lan < self.max_retries:
                    time.sleep(self.backoff_s * (2**lan))
                    continue
                raise loi_cuoi from None
            except TimeoutError:
                loi_cuoi = LLMTimeout(
                    f"Quá thời gian chờ {self.timeout_s:g}s khi gọi {self.model}"
                )
                if lan < self.max_retries:
                    continue
                raise loi_cuoi from None

        raise loi_cuoi or GeminiError("Gọi mô hình thất bại không rõ lý do")

    @staticmethod
    def _doc_loi(exc: urllib.error.HTTPError) -> str:
        """Đọc thân lỗi và CHE khóa trước khi cho nó đi bất cứ đâu."""
        try:
            than = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover - thân lỗi không đọc được
            than = str(exc)
        return mask_secrets(than)[:1000]

    # ----------------------------------------------------------------------
    # Trần token thật của model
    # ----------------------------------------------------------------------

    def output_limit(self) -> int:
        """Trần token đầu ra HIỆU LỰC — ``min(cấu hình, trần thật của model)``.

        AIS §2 nói rõ trần 200.000 là "hiệu lực = min(200.000, trần thực tế của
        model tại thời điểm gọi)". Điều này hóa ra không phải phòng xa: model
        thật hiện có trần 65.536, nên gửi thẳng 200.000 là gửi một con số model
        không nhận.

        Không tra được siêu dữ liệu thì giữ nguyên giá trị cấu hình và để nhà
        cung cấp báo lỗi — thà một thông báo lỗi rõ từ họ còn hơn ta tự đoán
        một trần rồi âm thầm cắt cụt phản hồi.
        """
        if self._tran_ra is not None:
            return min(self.max_output_tokens, self._tran_ra)

        # Tiêm lớp vận chuyển nghĩa là "client này KHÔNG được chạm mạng".
        # Không có luật này thì mọi bài test dùng lớp giả vẫn lặng lẽ gọi ra
        # ngoài để hỏi trần token — chậm, phụ thuộc mạng, và hỏng trong CI.
        lay = self.metadata_transport
        if lay is None and self.transport is None:
            lay = _urllib_get
        if lay is None:
            self._tran_ra = self.max_output_tokens
            return self.max_output_tokens

        try:
            thong_tin = lay(
                f"{self.base_url}/models/{self.model}", self.api_key, self.timeout_s
            )
            tran = int(thong_tin.get("outputTokenLimit", 0))
        except Exception:  # noqa: BLE001 - không tra được thì dùng cấu hình
            tran = 0

        self._tran_ra = tran or self.max_output_tokens
        return min(self.max_output_tokens, self._tran_ra)

    # ----------------------------------------------------------------------
    # Giao diện LLMClient
    # ----------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Đếm bằng bộ đếm của CHÍNH mô hình sẽ gọi — AIS §2.

        Không có khóa hoặc gọi thất bại thì lùi về ước lượng ngoại tuyến, và
        ước lượng ấy nghiêng về phía chặn nhầm. Lùi im lặng ở đây là chấp nhận
        được vì hậu quả xấu nhất là một prompt hợp lệ bị chặn — ngược lại thì
        không.
        """
        if not text:
            return 0
        try:
            phan_hoi = self._post(
                "countTokens",
                {"contents": [{"role": "user", "parts": [{"text": text}]}]},
            )
            return int(phan_hoi.get("totalTokens", 0)) or estimate_tokens(text)
        except (GeminiError, MissingApiKey, LLMTimeout):
            return estimate_tokens(text)

    def search_web(self, query: str, *, k: int = 8) -> list[dict[str, str]]:
        """Tìm trên web bằng công cụ tìm kiếm gắn sẵn của nhà cung cấp.

        Trả danh sách ``{"title", "url", "snippet"}``. Đây là **địa chỉ**, không
        phải **nội dung**: phần đọc nội dung do ``eaa/web.py`` làm, và làm qua
        bộ kiểm nguồn. Tách hai việc ấy là có chủ ý — một đoạn tóm tắt do mô
        hình viết lại trông y hệt một trích đoạn từ trang gốc, và đó đúng là
        loại nhầm lẫn AIS §12 gọi tên.

        Không đi qua ``_goi_mo_hinh``: lời gọi này không có ngân sách prompt để
        kiểm (câu truy vấn dài vài chục ký tự) và không sinh mã, nên ép nó vào
        khuôn ``Prompt`` chỉ thêm một lớp không dùng tới.
        """
        cau = (query or "").strip()
        if not cau:
            return []

        # ĐO ĐƯỢC trên model thật (30/08/2026): gửi thẳng câu truy vấn kèm công
        # cụ tìm kiếm thì model KHÔNG tìm — nó trả lời từ trí nhớ và
        # ``groundingMetadata`` rỗng. Cũng câu ấy, thêm một câu lệnh tìm rõ ràng
        # thì có 14–16 ``groundingChunks``. Công cụ được bật không có nghĩa là
        # công cụ được dùng, và đây đúng là kiểu hỏng im lặng tệ nhất: hàm vẫn
        # trả về, chỉ là trả về thứ lấy từ trí nhớ chứ không từ web. Nên câu
        # lệnh tìm nằm ở đây, trong adapter, không để bên gọi tự nhớ.
        chi_dan = (
            "Search the web for this and list the sources you used. "
            "Do not answer from memory.\n\n" + cau
        )

        phan_hoi = self._post(
            "generateContent",
            {
                "contents": [{"role": "user", "parts": [{"text": chi_dan}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.0, "candidateCount": 1},
            },
        )

        ung_vien = (phan_hoi.get("candidates") or [{}])[0]
        nen = ung_vien.get("groundingMetadata", {}) or {}
        ket: list[dict[str, str]] = []
        da_co: set[str] = set()
        for manh in nen.get("groundingChunks", []) or []:
            trang = manh.get("web") or {}
            url = (trang.get("uri") or "").strip()
            if not url or url in da_co:
                continue
            da_co.add(url)
            ket.append({
                "title": (trang.get("title") or "").strip(),
                "url": url,
                "snippet": "",
            })
            if len(ket) >= k:
                break

        # Đoạn văn mô hình viết ra được gắn vào ô snippet của kết quả mà nó
        # trích — để người đọc thấy vì sao địa chỉ này được nêu, chứ không để
        # dùng thay nội dung trang.
        phan = (ung_vien.get("content", {}) or {}).get("parts", []) or []
        tom = "".join(p.get("text", "") for p in phan).strip()
        if tom and ket:
            ket[0]["snippet"] = tom[:600]
        return ket

    def complete(self, prompt: Prompt) -> str:
        """Gọi mô hình và trả VĂN BẢN THÔ, không đòi khối ```file:.

        Không phải mọi lời gọi đều là sinh mã. Tra cứu công cụ, phân loại lỗi,
        phân tích số đo tại G4 — đều là câu hỏi văn xuôi, và bắt chúng trả về
        khối tệp thì mọi phản hồi đúng đắn đều bị tính là hỏng định dạng.
        """
        van_ban, _, _ = self._goi_mo_hinh(prompt)
        return van_ban

    def generate(self, prompt: Prompt) -> CodeArtifact:
        """Gọi mô hình và bóc tách phản hồi thành artifact mã nguồn."""
        van_ban, tokens_in, tokens_out = self._goi_mo_hinh(prompt)
        files = parse_file_blocks(van_ban)
        return CodeArtifact(
            files=files,
            prompt_hash=prompt.hash,
            model=self.model,
            constraints_version=prompt.constraints_version,
            chunk_ids=list(prompt.chunk_ids),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            raw_response=van_ban,
        )

    def _goi_mo_hinh(self, prompt: Prompt) -> tuple[str, int, int]:
        """Phần dùng chung của ``complete`` và ``generate``."""
        prompt.check_budget(self.count_tokens)

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt.render()}]}],
            "generationConfig": {
                "temperature": prompt.temperature or self.temperature,
                "maxOutputTokens": self.output_limit(),
                # Tất định hết mức nhà cung cấp cho phép: mã nhúng cần tái lập.
                "topP": 1.0,
                "candidateCount": 1,
            },
        }
        if prompt.system_instruction:
            # AIS §2: Gemini tách system instruction khỏi nội dung người dùng —
            # tận dụng để lớp ràng buộc không bị "trôi" giữa cuộc.
            payload["systemInstruction"] = {
                "parts": [{"text": prompt.system_instruction}]
            }

        bat_dau = time.monotonic()
        phan_hoi = self._post("generateContent", payload)
        thoi_gian = time.monotonic() - bat_dau

        van_ban = self._lay_van_ban(phan_hoi)
        su_dung = phan_hoi.get("usageMetadata", {}) or {}
        tokens_in = int(su_dung.get("promptTokenCount", 0)) or self.count_tokens(
            prompt.full_text()
        )
        tokens_out = int(su_dung.get("candidatesTokenCount", 0)) or estimate_tokens(van_ban)

        if self.call_log is not None:
            self.call_log.record(
                prompt=prompt,
                response=van_ban,
                model=self.model,
                provider=self.provider,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_s=thoi_gian,
            )

        return van_ban, tokens_in, tokens_out

    @staticmethod
    def _lay_van_ban(phan_hoi: dict[str, Any]) -> str:
        """Bóc phần văn bản; nói rõ khi mô hình từ chối hoặc bị cắt cụt.

        Ba tình huống dưới đây đều trả về "không có mã", nhưng vì ba lý do
        hoàn toàn khác nhau — gộp chúng thành một thông báo chung sẽ khiến
        người gỡ rối đi sai hướng.
        """
        ung_vien = phan_hoi.get("candidates") or []
        if not ung_vien:
            phan_hoi_chan = phan_hoi.get("promptFeedback", {}) or {}
            ly_do = phan_hoi_chan.get("blockReason")
            if ly_do:
                raise GeminiError(
                    f"Mô hình từ chối xử lý prompt (lý do: {ly_do}). Prompt của "
                    "quy trình này chỉ chứa ràng buộc, trích đoạn tài liệu kỹ "
                    "thuật và mô tả nhiệm vụ — nếu bị chặn, kiểm lại phần trích "
                    "đoạn vừa nạp."
                )
            raise GeminiError("Mô hình không trả về ứng viên nào")

        dau = ung_vien[0]
        ly_do_dung = dau.get("finishReason", "")
        phan = (dau.get("content", {}) or {}).get("parts", []) or []
        van_ban = "".join(p.get("text", "") for p in phan)

        if ly_do_dung == "MAX_TOKENS":
            raise GeminiError(
                "Phản hồi bị cắt vì chạm trần token đầu ra. Trần đang đặt rất cao "
                "theo AIS §2 nên chạm trần là dấu hiệu nhiệm vụ quá lớn cho một "
                "module — chia nhỏ module thay vì nâng trần."
            )
        if not van_ban.strip():
            raise GeminiError(
                f"Mô hình trả về nội dung rỗng (finishReason={ly_do_dung!r}). "
                "Tính là một lần fail của vòng tự sửa (SDD §6)."
            )
        return van_ban
