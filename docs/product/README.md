# Thiết kế sản phẩm OpenInterview

Website dùng tiếng Anh đơn giản ở mọi trang và trạng thái; chỉ hội thoại phỏng vấn nói bằng tiếng Việt. Transcript và bằng chứng nguyên văn giữ ngôn ngữ gốc như dữ liệu nguồn, không dịch đè. Xem [quy tắc ngôn ngữ UI](ui-spec.md#ngon-ngu-ui). Không thêm language picker hoặc dependency i18n.

- [Đặc tả UI theo từng trang](ui-spec.md): giải thích bằng tiếng Việt; nội dung website bằng tiếng Anh, route đề xuất, quyền, trạng thái, hành trình và đối chiếu MVP.
- [Prompt tạo thiết kế](design-generation-prompt.md): sao chép toàn bộ nội dung trong khối prompt để dùng với công cụ thiết kế; đính kèm bốn ảnh tham chiếu nếu công cụ hỗ trợ.

Đây là **đề xuất thiết kế, chưa triển khai hoặc nghiệm thu UI**. Tài liệu đồng bộ [yêu cầu MVP](../business/requirements.md), không đánh dấu hoàn thành [sprint](../planning/sprint-plan.md).

Đúng 7 page types, mỗi loại một frame desktop 1440: Home `/`; Sign in `/login`; Roles `/roles`; Join room `/rooms/{id}`; Interview `/sessions/{id}/interview`; HR `/hr`; Admin `/admin`. Callback là system transition; waiting/consent/errors inline, HR tabs/forms dùng cùng workspace. Mobile/tablet/responsive OUT OF SCOPE.

Home chỉ navbar 56 px với logo 30 px + hero title/subtitle và hai CTA + một robot preview chỉ có “Voice interview”, robot và “Interview language: Vietnamese”, dừng đúng blue box. Preview tĩnh chỉ được mô tả trong annotations, không thêm UI copy hoặc tuyên bố phỏng vấn live. Không hero badge, Example chip, AI-speaking/waveform hoặc bottom disclaimer. Interview chỉ một robot stage + đúng ba controls mic, speaker, End. End trực tiếp trả Roles với “Interview ended”. Không candidate profile/history/settings/CV portal, không recording/export trong active MVP. HR có thể upload CV tùy chọn khi tạo room; khóa candidate/campaign/attachment khi publish, sửa sai sau đó phải revoke/cancel và tạo room mới. Không file là “No CV attached”, không chặn candidate. Private CV storage/scanning và lawful basis trước upload là yêu cầu backend, không thêm dashboard.

Phong cách dựa trên mô tả bốn screenshot của người dùng trong handoff; không phải token/layer trích xuất từ Figma. Quyền dùng lại tài sản cần được kiểm tra. Các route, token màu, giới hạn upload và bố cục đều là đề xuất cần xác nhận.
