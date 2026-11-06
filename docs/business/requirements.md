# Yêu cầu MVP — bản Dev/Lead

## Phạm vi và vai trò

Trong phạm vi: tạo chiến dịch từ JD + yêu cầu recruiter + FAQ/context nội bộ đã duyệt; duyệt câu hỏi trước phiên; phỏng vấn browser voice tiếng Việt; Q&A có căn cứ; báo cáo bất đồng bộ và người duyệt. Vai trò: candidate chỉ truy cập phiên được cấp; recruiter chỉ quản lý chiến dịch được phân quyền; operator quản lý cấu hình và vận hành, không mặc nhiên có quyền xem mọi nội dung.

Ngoài phạm vi: PSTN/SIP/số điện thoại, CV bắt buộc từ candidate, candidate profile/CV upload/change/version/share/history/settings portal, mobile/tablet/responsive frames/tasks, recording/export active MVP, coding test, thi kỹ thuật nặng, tự quyết định tuyển, Gemini Live, tìm kiếm web chính sách, vector DB và truy cập rộng hệ thống nội bộ. HR CV upload tùy chọn khi tạo room vẫn trong scope; không CV parsing/scoring/AI prompt input.

Đúng 7 page types desktop, mỗi loại một frame 1440: Home `/`, Sign in `/login`, Roles `/roles`, Join room `/rooms/{id}`, Interview `/sessions/{id}/interview`, HR `/hr`, Admin `/admin`. Consent/device/waiting/errors inline Join room, callback là transition. Home chỉ navbar logo/Roles/Sign in, hero hai CTA và một robot preview Example; không section khác. HR chỉ Campaigns/Rooms/Reports tabs với forms inline/drawer; Admin users/HR grants + service health và expandable audit metadata. Policies/contacts đọc được trong sign-in/join trước consent, không bỏ disclosure để giảm trang. Xem [UI spec](../product/ui-spec.md).

## Quy tắc có thể kiểm thử

| ID | Yêu cầu và điều kiện nghiệm thu |
| --- | --- |
| R01 | Sinh bộ câu hỏi từ JD trước phiên; recruiter phải duyệt câu hỏi, rubric, FAQ. Chặn mở phiên nếu chưa duyệt; phiên ghim phiên bản đã khóa. Thay đổi tạo phiên bản mới, không sửa hồi tố. |
| R02 | Mở đầu công bố AI, mục đích, chính sách transcript và quyền dừng; lưu phiên bản thông báo, thời điểm và lựa chọn đồng ý. Không đồng ý thì không bắt đầu phỏng vấn. Chỉ kiểm tra mic sau lựa chọn phù hợp; không thu nội dung phỏng vấn trước consent. |
| R03 | Hỏi từng câu theo các pha đã định; controller thực thi số followup tối đa 1–2/chủ đề và ngân sách phiên cấu hình (baseline 8–12 phút). Câu làm rõ STT có loại riêng và giới hạn riêng để tránh lặp vô hạn. |
| R04 | Candidate được skip, clarify, interrupt, end và sửa câu trả lời qua voice/controller. Interview một stage + đúng ba controls mic mute/unmute, speaker mute/unmute, End interview; status/error ngắn trong stage, không timer/captions/extra controls. End hiệu lực ngay mọi pha, dừng media/cancel output không confirm/forced wrap, trả Roles với “Interview ended”, không hứa xóa. Không tự điền trường thiếu. Phân biệt `not_collected`, `refused`, `insufficient_evidence`, `supported`; mức năng lực thấp chỉ khi có bằng chứng theo rubric. |
| R05 | Trường cá nhân có cấu hình bắt buộc/tùy chọn và lý do; mặc định các trường nhạy cảm không bắt buộc. Tuổi chỉ bật sau kiểm tra lý do, consent và pháp lý; không DOB/địa chỉ chính xác, không chấm điểm tuổi. |
| R06 | Câu hỏi lõi/rubric dùng chung trong chiến dịch. Followup chỉ lấy bằng chứng cho tiêu chí đã duyệt, không tăng độ khó tùy ứng viên; chưa hỏi không tương đương không đạt. |
| R07 | FAQ chỉ trả lời từ nguồn đã duyệt, đúng hiệu lực. Unknown/conflict/expired phải trả lời chưa xác nhận và tạo recruiter followup. Dashboard lưu source IDs; không đọc mã nguồn thành tiếng. |
| R08 | Transcript cuối cùng là bằng chứng; lời AI bị ngắt chỉ lưu phần xác nhận đã phát tới candidate. Nội dung chưa xác nhận phát xong không được tính là câu đã hỏi. Giữ provenance và correction thay vì sửa mất lịch sử. |
| R09 | Mọi API kiểm tra quyền theo chiến dịch/phiên. Backend giữ credential; browser chỉ nhận LiveKit token TTL ngắn, room/identity và quyền tối thiểu. Không ghi secret vào log. |
| R10 | Recording/export ngoài active MVP, không capture bền/controls. Transcript/report/room CV có quyền/retention/xóa riêng, kể cả demo. HR authority/lawful basis/notice trước upload CV tách consent phiên về sau. CV cần private storage, server validation/quarantine/scan trước publish; không scan không publish room có file. Xóa copies/backups theo giới hạn công bố, tombstone ngăn job/restore hồi sinh. Không log PII đầy đủ. |
| R11 | Kết thúc phiên tạo job báo cáo bền vững trong DB; restart không mất job, retry không tạo báo cáo trùng. Báo cáo cần người duyệt; không có hành động tuyển tự động. |
| R12 | Chặn hỏi thông tin định danh/tài chính/sức khỏe/gia đình nhạy cảm không cần thiết; chỉ hỏi trường phù hợp có lý do và phê duyệt. Candidate từ chối không bị trừ điểm hay suy ra năng lực thấp. Nếu tự kể, AI không hỏi sâu/nhắc lại chi tiết, giảm thiểu theo R10 và không hứa xóa chưa được thực hiện. Kiểm tra cả câu hỏi sinh trước phiên và followup. |
| R13 | Không tiết lộ credential, dữ liệu ứng viên khác, câu hỏi phỏng vấn/khóa chấm điểm mật, kể cả khi có trong context. Nói rõ giới hạn tiết lộ khác với chưa biết; cung cấp bước tiếp theo an toàn. Câu hỏi lương/phúc lợi thông thường không tự động bị cấm; áp dụng R07. |
| R14 | Chỉ khẳng định chi tiết sẽ được giải đáp ở vòng sau nếu nguồn đã duyệt còn hiệu lực xác nhận rõ; không ngụ ý đã qua vòng, bảo đảm vòng tiếp theo hay liên hệ. Không có căn cứ thì nói chưa xác nhận, ghi recruiter followup, không hứa hạn trả lời. Câu hỏi pha sau được hỏi sớm vẫn được trả lời ngắn nếu có nguồn hoặc xin phép trì hoãn; không ép im lặng theo pha. |
| R15 | Model diễn đạt ngắn, tự nhiên từ hành động/lý do và nguồn được controller cho phép; không tự tạo policy/lời hứa. Từ chối có lý do trung thực và bước tiếp theo, xin phép quay lại phỏng vấn, không trách móc/lặp vô hạn. Speech/JD không ghi đè policy. Kiểm tra schema không đủ chứng minh an toàn ngữ nghĩa; phải qua case nội dung ở kế hoạch kiểm chứng. Guardrail không thêm status vào FAQAnswer hay action enum; metadata/ánh xạ lưu trữ cần chốt trước triển khai. |

## Hợp đồng dữ liệu tối thiểu

| Thực thể | Trường chính |
| --- | --- |
| CampaignVersion | campaign_id, version, JD, screening_criteria, core_questions, rubric, approved_by/at, time_budget, followup_limits |
| FAQSource | source_id, version, campaign_version, content, effective_from/to, approved_by/at, status |
| Room (đề xuất) | id, candidate_identity + email/name binding, role, campaign_version, schedule/window/timezone, contact, status, cv_attachment_id nullable, published_at; publish/invite khóa identity/campaign/CV version/hash hoặc absence |
| CVAttachment (đề xuất) | id, room_id, candidate_identity, immutable version, private object_key, sha256, size_bytes, validated MIME/type, scan_status, uploaded_by/at, HR authority/lawful_basis_notice_ref, retention_until, tombstone; không CV library |
| Session | id, room_id + immutable room binding, campaign_version, candidate_identity, consent_record, phase, status, started/ended_at, retention_until; recording disabled trong MVP |
| CandidateFact | field, value nullable, collection_status, evidence_turn_ids, correction_of nullable |
| Turn | id, session_id, speaker, finalized_text, kind, timestamps, delivery_status; assistant chỉ có text đã xác nhận phát |
| CandidateQuestion | id, session_id, turn_id, text, topic |
| FAQAnswer | question_id, status: answered/unknown/conflict/expired, answer_text, source_versions, followup_status |
| ReportJob / Report | session_id, input_version, status, attempts, lease_until, report_version, evidence, reviewer/status |

Giá trị không thu thập dùng null + trạng thái, không bịa giá trị mặc định. Hợp đồng triển khai chi tiết, loại ID, ràng buộc DB và API còn phải chốt; đây không phải schema migration đã có.

Giả định: user không bắt buộc CV; HR upload được hỗ trợ, `cv_attachment_id = null` / “No CV attached” hợp lệ, không chặn publish/join nếu cổng khác pass. Server kiểm tra candidate/room relationship và bounded PDF (5 MB configurable proposal; extension/MIME/signature/size, không client-only). File quarantine tới scan thành công; lỗi/không scan chặn publish room chứa file. HR sửa draft được; publish/invite khóa attachment và absence, không silent overwrite. Sai CV sau đó => revoke/cancel room cũ, tạo NEW room, không swap ongoing session/source history. Candidate không upload/manage/download mặc định, báo mismatch qua HR contact inline trước start. CV claims chưa xác minh; report metadata có thể ghim ref/hash nhưng không là finalized candidate turn/evidence hoặc AI input. Private object store bắt buộc cho CV retained, URL TTL ngắn sau fresh auth assigned HR/worker khi cần, secrets server-only; retention/xóa bao trùm room/CV copies/backups và tombstones. Xem [vòng đời](../architecture/data-artifacts.md).

## Lỗi và fallback

Mic bị chặn: hướng dẫn cấp quyền/thử lại, cho phép dừng. STT không chắc tên/số/phủ định: hỏi xác nhận, không suy diễn. Provider timeout: báo ngắn, retry hữu hạn rồi kết thúc có lý do; không tạo câu trả lời giả. Mất kết nối: đánh dấu gián đoạn, chỉ tiếp tục nếu khôi phục đúng phiên và trạng thái; không tự tạo phiên trùng. Hết ngân sách: ưu tiên wrap và đánh dấu phần thiếu. FAQ lỗi: nhận câu hỏi và chuyển recruiter. Báo cáo lỗi: giữ trạng thái pending/failed có thể retry, không hiển thị như hoàn tất.

Chi tiết điều phối: [hội thoại](../architecture/conversation-workflow.md). Định nghĩa đầu ra: [báo cáo](../report/interview-report.md). Các yêu cầu trên là tiêu chí cần xây và kiểm chứng, chưa được xác nhận bằng ứng dụng thực tế.
