# Yêu cầu MVP — bản Dev/Lead

## Phạm vi và vai trò

Trong phạm vi: tạo chiến dịch từ JD + yêu cầu recruiter + FAQ/context nội bộ đã duyệt; duyệt câu hỏi trước phiên; phỏng vấn browser voice tiếng Việt; Q&A có căn cứ; báo cáo bất đồng bộ và người duyệt. Vai trò: candidate chỉ truy cập phiên được cấp; recruiter chỉ quản lý chiến dịch được phân quyền; operator quản lý cấu hình và vận hành, không mặc nhiên có quyền xem mọi nội dung.

Ngoài phạm vi: PSTN/SIP/số điện thoại, CV bắt buộc, coding test, thi kỹ thuật nặng, tự quyết định tuyển, Gemini Live, tìm kiếm web chính sách, vector DB và truy cập rộng hệ thống nội bộ.

## Quy tắc có thể kiểm thử

| ID | Yêu cầu và điều kiện nghiệm thu |
| --- | --- |
| R01 | Sinh bộ câu hỏi từ JD trước phiên; recruiter phải duyệt câu hỏi, rubric, FAQ. Chặn mở phiên nếu chưa duyệt; phiên ghim phiên bản đã khóa. Thay đổi tạo phiên bản mới, không sửa hồi tố. |
| R02 | Mở đầu công bố AI, mục đích, chính sách transcript và quyền dừng; lưu phiên bản thông báo, thời điểm và lựa chọn đồng ý. Không đồng ý thì không bắt đầu phỏng vấn. Chỉ kiểm tra mic sau lựa chọn phù hợp; không thu nội dung phỏng vấn trước consent. |
| R03 | Hỏi từng câu theo các pha đã định; controller thực thi số followup tối đa 1–2/chủ đề và ngân sách phiên cấu hình (baseline 8–12 phút). Câu làm rõ STT có loại riêng và giới hạn riêng để tránh lặp vô hạn. |
| R04 | Candidate được skip, clarify, interrupt, end và sửa câu trả lời. Không tự điền trường thiếu. Phân biệt `not_collected`, `refused`, `insufficient_evidence`, `supported`; mức năng lực thấp chỉ gán khi có bằng chứng theo rubric. |
| R05 | Trường cá nhân có cấu hình bắt buộc/tùy chọn và lý do; mặc định các trường nhạy cảm không bắt buộc. Tuổi chỉ bật sau kiểm tra lý do, consent và pháp lý; không DOB/địa chỉ chính xác, không chấm điểm tuổi. |
| R06 | Câu hỏi lõi/rubric dùng chung trong chiến dịch. Followup chỉ lấy bằng chứng cho tiêu chí đã duyệt, không tăng độ khó tùy ứng viên; chưa hỏi không tương đương không đạt. |
| R07 | FAQ chỉ trả lời từ nguồn đã duyệt, đúng hiệu lực. Unknown/conflict/expired phải trả lời chưa xác nhận và tạo recruiter followup. Dashboard lưu source IDs; không đọc mã nguồn thành tiếng. |
| R08 | Transcript cuối cùng là bằng chứng; lời AI bị ngắt chỉ lưu phần xác nhận đã phát tới candidate. Nội dung chưa xác nhận phát xong không được tính là câu đã hỏi. Giữ provenance và correction thay vì sửa mất lịch sử. |
| R09 | Mọi API kiểm tra quyền theo chiến dịch/phiên. Backend giữ credential; browser chỉ nhận LiveKit token TTL ngắn, room/identity và quyền tối thiểu. Không ghi secret vào log. |
| R10 | Audio off mặc định; opt-in riêng nếu bật. Transcript/audio/report có thời hạn lưu, quyền xem và xóa theo chính sách đã công bố, kể cả demo. Không đưa nội dung cá nhân đầy đủ vào log vận hành. |
| R11 | Kết thúc phiên tạo job báo cáo bền vững trong DB; restart không mất job, retry không tạo báo cáo trùng. Báo cáo cần người duyệt; không có hành động tuyển tự động. |

## Hợp đồng dữ liệu tối thiểu

| Thực thể | Trường chính |
| --- | --- |
| CampaignVersion | campaign_id, version, JD, screening_criteria, core_questions, rubric, approved_by/at, time_budget, followup_limits |
| FAQSource | source_id, version, campaign_version, content, effective_from/to, approved_by/at, status |
| Session | id, campaign_version, candidate_identity, consent_record, audio_opt_in, phase, status, started/ended_at, retention_until |
| CandidateFact | field, value nullable, collection_status, evidence_turn_ids, correction_of nullable |
| Turn | id, session_id, speaker, finalized_text, kind, timestamps, delivery_status; assistant chỉ có text đã xác nhận phát |
| CandidateQuestion | id, session_id, turn_id, text, topic |
| FAQAnswer | question_id, status: answered/unknown/conflict/expired, answer_text, source_versions, followup_status |
| ReportJob / Report | session_id, input_version, status, attempts, lease_until, report_version, evidence, reviewer/status |

Giá trị không thu thập dùng null + trạng thái, không bịa giá trị mặc định. Hợp đồng triển khai chi tiết, loại ID, ràng buộc DB và API còn phải chốt; đây không phải schema migration đã có.

## Lỗi và fallback

Mic bị chặn: hướng dẫn cấp quyền/thử lại, cho phép dừng. STT không chắc tên/số/phủ định: hỏi xác nhận, không suy diễn. Provider timeout: báo ngắn, retry hữu hạn rồi kết thúc có lý do; không tạo câu trả lời giả. Mất kết nối: đánh dấu gián đoạn, chỉ tiếp tục nếu khôi phục đúng phiên và trạng thái; không tự tạo phiên trùng. Hết ngân sách: ưu tiên wrap và đánh dấu phần thiếu. FAQ lỗi: nhận câu hỏi và chuyển recruiter. Báo cáo lỗi: giữ trạng thái pending/failed có thể retry, không hiển thị như hoàn tất.

Chi tiết điều phối: [hội thoại](../architecture/conversation-workflow.md). Định nghĩa đầu ra: [báo cáo](../report/interview-report.md). Các yêu cầu trên là tiêu chí cần xây và kiểm chứng, chưa được xác nhận bằng ứng dụng thực tế.
