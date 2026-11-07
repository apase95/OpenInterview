# OpenInterview — tài liệu MVP

Đây là thiết kế đề xuất cho sản phẩm độc lập, chưa phải mô tả một ứng dụng đã triển khai. Phỏng vấn giọng nói chạy trong trình duyệt, không gọi điện thoại. Website UI/UX hoàn toàn bằng tiếng Anh; chỉ hội thoại phỏng vấn nói bằng tiếng Việt. Tài liệu có thể giải thích bằng tiếng Việt. Transcript và bằng chứng nguyên văn giữ tiếng Việt như dữ liệu nguồn, không dịch đè; xem [quy tắc ngôn ngữ UI](product/ui-spec.md#ngon-ngu-ui).

## Contributor guides

- [Getting started](contributing/getting-started.md): local Docker setup.
- [Development guide](contributing/development.md): commands, checks, and limits.
- [Conventions](contributing/conventions.md): code, pull requests, and safe data handling.

## Tài liệu sản phẩm và kế hoạch

| Tài liệu | Người đọc và mục đích |
| --- | --- |
| [Tổng quan nghiệp vụ](business/overview.md) | Kinh doanh, kinh tế, tuyển dụng: giá trị, giới hạn và hành trình |
| [Yêu cầu sản phẩm](business/requirements.md) | Dev/Lead: quy tắc, dữ liệu và điều kiện nghiệm thu |
| [Kiến trúc và công nghệ](architecture/system-architecture.md) | Thành phần, triển khai, bảo mật và lựa chọn nhà cung cấp |
| [Điều phối hội thoại](architecture/conversation-workflow.md) | Trạng thái, streaming, ngắt lời và FAQ |
| [Hợp đồng I/O](architecture/io-contracts.md) | Nguồn vào, audio trả về, event/turn và xử lý gián đoạn |
| [API/data contract v1](architecture/api-data-contract.md) | Shared technical baseline, generated OpenAPI, synthetic fixtures and guarded dev/test DB slice; domain routes not implemented |
| [Artifact và vòng đời dữ liệu](architecture/data-artifacts.md) | Transcript, room CV private storage, quyền/retention; recording/export chỉ tương lai |
| [Kế hoạch kiểm chứng](planning/validation-plan.md) | Các giai đoạn, ma trận kiểm thử, rủi ro và quyết định còn mở |
| [Checklist triển khai theo vai trò](planning/implementation-checklist.md) | BA, DevOps, Fullstack Developer, AI Engineer: các việc cần làm cho MVP |
| [Kế hoạch theo sprint](planning/sprint-plan.md) | Sáu sprint đề xuất, task chi tiết, phụ thuộc và cổng nghiệm thu |
| [Báo cáo sau phiên](report/interview-report.md) | Bằng chứng, xử lý bền vững và người duyệt |
| [Thiết kế sản phẩm](product/README.md) | Phạm vi UI đề xuất, ưu tiên và tài liệu thiết kế |
| [Đặc tả UI theo từng trang](product/ui-spec.md) | Route, quyền, nội dung website tiếng Anh, component, trạng thái và hành trình |
| [Prompt tạo thiết kế](product/design-generation-prompt.md) | Prompt độc lập có thể sao chép để tạo UI/prototype theo tham chiếu |

Quy ước: “chiến dịch” là đợt tuyển cho một vai trò; “câu hỏi lõi” là bộ câu hỏi được duyệt và dùng chung trong chiến dịch; “phiên bản khóa” không thay đổi đối với phiên đang chạy. Mọi ngưỡng thời gian, lưu trữ và chi phí cần được xác nhận trước khi dùng thật. Không có quyết định tuyển dụng tự động.

UI MVP đúng 7 page types desktop (một frame 1440 mỗi loại): Home `/`, Sign in `/login`, Roles `/roles`, Join room `/rooms/{id}`, Interview `/sessions/{id}/interview`, HR `/hr`, Admin `/admin`. Home chỉ navbar 56 px với logo 30 px/hero title, subtitle và hai CTA/robot preview chỉ có “Voice interview”, robot và “Interview language: Vietnamese”; preview tĩnh chỉ mô tả trong annotations, không thêm UI copy hoặc tuyên bố phỏng vấn live. Không hero badge, Example chip, AI-speaking/waveform hoặc bottom disclaimer. Interview chỉ stage + đúng ba controls mic/speaker/End; End trực tiếp về Roles inline “Interview ended”. Consent/devices/waiting/errors inline, không extra frames. Mobile/tablet/responsive, candidate profile/history/settings/CV portal và recording/export active MVP đều OUT OF SCOPE. HR có thể upload CV tùy chọn khi tạo room; missing “No CV attached” được phép. Publish/invite khóa exact identity/campaign/attachment ID/version/hash hoặc absence; sai CV sau đó revoke/cancel + NEW room. Private CV storage, server validation/quarantine/scan trước publish và HR authority/lawful basis/notice trước upload bắt buộc; CV không prompt/scoring/evidence. Xem [UI spec](product/ui-spec.md) và [contract](business/requirements.md).
