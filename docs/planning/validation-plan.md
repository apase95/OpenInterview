# Kế hoạch triển khai và kiểm chứng

## Các cổng nghiệm thu

Không ấn định lịch hoặc giá khi chưa có số liệu. Mỗi giai đoạn chỉ qua cổng khi có artifact và người chịu trách nhiệm duyệt.

| Giai đoạn | Artifact | Điều kiện qua cổng |
| --- | --- | --- |
| 1. Mô phỏng text | Campaign mẫu, câu hỏi/rubric được duyệt, FAQ versioned, transcript giả lập và báo cáo | Tất cả case policy bắt buộc bên dưới pass; controller chặn vượt hạn mức; mọi nhận định có evidence hoặc trạng thái thiếu; không ra quyết định tuyển |
| 2. Browser audio | Luồng mic → STT → LLM → TTS, consent, interruption, lưu turn và trace thời gian | Kiểm tra browser/mạng mục tiêu; không nói lại chunk cũ sau ngắt; lưu đúng phần đã phát; không mất/trùng phiên khi reconnect; đo latency và lỗi STT thay vì tuyên bố đạt sẵn |
| 3. Demo nội bộ | Dữ liệu synthetic, dashboard người duyệt, job restart/retry, retention và bảng chi phí | Job đang chạy phục hồi sau restart và chỉ có một kết quả cho cùng input; kiểm tra quyền âm tính pass; xóa dữ liệu mẫu đúng chính sách; recruiter duyệt usefulness và các lỗi còn chấp nhận được |

## Ma trận kiểm thử tối thiểu

| Tình huống | Kỳ vọng / bằng chứng cần giữ |
| --- | --- |
| Luồng bình thường | Đủ consent → các pha → wrap; câu lõi đúng phiên bản; báo cáo liên kết turn |
| Giọng Bắc/Trung/Nam, code switching Việt–Anh | Bộ mẫu có transcript chuẩn; thống kê lỗi từ và lỗi entity/phủ định riêng theo nhóm, không chỉ trung bình tổng |
| Nhiễu, echo, ngập ngừng và im lặng | Không cắt câu chỉ vì ngừng ngắn; hỏi xác nhận khi cần; timeout hữu hạn và lý do dừng |
| Tên, số năm, “không/chưa” bị nhận sai | Xác nhận hoặc sửa có provenance; không chấm dựa trên partial/sai đã được sửa |
| FAQ known | Đáp án chỉ có thông tin được nguồn hợp lệ hỗ trợ; source IDs/version ở dashboard |
| FAQ unknown/conflict/expired | Không bịa/hứa; nói chưa xác nhận và tạo followup tương ứng |
| Từ chối consent hoặc ghi âm | Từ chối phỏng vấn thì dừng; từ chối audio recording vẫn dùng được phiên với transcript nếu đã consent phần đó |
| Skip, từ chối tuổi, sửa thông tin | Phân biệt refused/not_collected/insufficient_evidence; không chấm tuổi, không tự điền |
| Followup và clarification liên tiếp | Controller chặn vượt từng loại hạn mức; giữ cùng rubric; deadline đưa về wrap |
| Nói chen và kết thúc sớm | Audio chờ bị hủy; không phát output cũ; chỉ lưu phần đã phát; dừng được ở mọi pha |
| Prompt injection trong speech/context không tin cậy | Không đổi rubric, policy, nguồn FAQ hoặc lộ secret; không truy cập web/nội bộ |
| Mic denied, mạng yếu, disconnect, provider timeout/quota | Hướng dẫn rõ, retry hữu hạn; trạng thái interrupted/ended chính xác, không nhân đôi phiên |
| Worker chết khi tạo report; job được xử lý hai lần | Lease hết hạn được nhận lại; unique key ngăn kết quả trùng; report không hoàn tất nửa chừng |
| Token hết hạn, truy cập chéo chiến dịch | Từ chối quyền; refresh chỉ sau kiểm tra phiên; không credential trong browser/log |
| Retention và xóa | Transcript/report/audio opt-in bị xử lý đúng thời hạn, quyền và quy trình backup đã công bố |

Baseline nghiệm thu policy: không có vi phạm trong tập case đã duyệt; điều này không chứng minh hệ thống không bao giờ vi phạm. Lưu phiên bản test, cấu hình model/SDK, số mẫu, kết quả và lỗi còn mở. Với đánh giá voice, recruiter/người bản ngữ đối chiếu transcript và listening sample có consent riêng; ưu tiên audio synthetic.

## Chỉ số và quyết định còn mở

- Latency: đo p50/p95 end-of-speech → first audible playback, endpointing và từng chặng; mục tiêu chưa đo ở [kiến trúc](../architecture/system-architecture.md). Báo rõ cỡ mẫu, mạng, browser, vùng và concurrency.
- Chất lượng: tỷ lệ cắt sai, ngắt lời thành công, STT entity/negation, FAQ có nguồn, refusal đúng và báo cáo có evidence; chốt ngưỡng chất lượng với recruiter trước pilot.
- Chi phí/call: tổng LiveKit, STT, LLM, TTS, hạ tầng theo thời lượng thực và token/ký tự; tính cả retry, không suy từ bảng giá đơn lẻ thành cam kết.
- Cần chốt: model/voice/region khả dụng; browser hỗ trợ; TTL token; clarification/retry/reconnect budget; concurrency; retention và consent wording; người duyệt FAQ và hiệu lực; phương pháp xác nhận playback; bộ mẫu/ngưỡng chất lượng.
- Rủi ro: accent bias, STT mất phủ định, hallucination chính sách, audio cắt sai, lộ dữ liệu, provider thay đổi và report job mắc kẹt. Chủ sở hữu lần lượt là recruiter + kỹ thuật chất lượng, backend/security và operator; trước pilot cần gán cá nhân cụ thể.

Không có app code hoặc kết quả chạy sản phẩm trong bộ tài liệu. Kiểm tra tài liệu không thay thế các cổng nghiệm thu này.
