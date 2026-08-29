"""LLM Core — adapter hoán đổi được giữa các nhà cung cấp (ADR-03).

Orchestrator không được biết mình đang nói chuyện với mô hình nào: Chương 3
cần so sánh nhiều mô hình trên cùng một quy trình, nên đổi mô hình phải là đổi
một dòng cấu hình chứ không phải sửa vòng lặp (FR-LLM-01, TC-11).

MockLLM ở ``mock.py`` là một adapter thật sự ngang hàng, không phải nhánh rẽ
trong engine — nhờ vậy thứ được kiểm thử ở Sprint 1–3 chính là thứ sẽ chạy với
mô hình thật ở Sprint 4.
"""
