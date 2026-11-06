# Báo cáo sau phiên và người duyệt

Định dạng xuất, ví dụ synthetic và vòng đời nằm tại [artifact dữ liệu](../architecture/data-artifacts.md); phân biệt text tạo ra với lời đã phát tại [hợp đồng I/O](../architecture/io-contracts.md).

## Đầu ra đề xuất

Báo cáo bất đồng bộ sau cuộc gọi, không cần live scoring. Mỗi bản ghim session, campaign/rubric version, input transcript version, model/config version và thời điểm tạo.

Trong đúng [7 trang desktop](../product/README.md), report là Reports tab + inline detail/drawer ở `/hr`, không route/frame riêng. UI/summary/notes English, nguyên văn evidence Vietnamese, không dịch đè source. Recording/export ngoài active MVP, không download/audio controls. `candidate-profile.json` chỉ machine-derived fact artifact, không candidate profile portal.

Report provenance ghim immutable room identity/campaign và optional CV attachment ID/version/hash hoặc absence; “No CV attached” hợp lệ và không là tiêu chí bất lợi. CV HR upload lúc tạo room chỉ để HR tham khảo, claims chưa xác minh, không parse/score/nạp prompt hoặc cite thành finalized candidate turn. HR lawful basis/notice/authority trước upload tách consent phiên; private object store và validation/quarantine/scan trước publish bắt buộc. Sau publish sai file => revoke/cancel room và tạo NEW room, không swap ongoing history. Chi tiết [contract/lifecycle](../architecture/data-artifacts.md#room-cv--active-mvp).

1. Tình trạng phiên: hoàn tất/gián đoạn/kết thúc sớm và phần chưa hỏi.
2. Thông tin ứng viên tự cung cấp, trạng thái từng trường, correction gần nhất và turn bằng chứng; không suy đoán học vấn, tuổi hoặc kinh nghiệm.
3. Tóm tắt theo tiêu chí rubric: nhận định ngắn, trích đoạn finalized transcript và turn IDs, mức đánh giá nếu đủ căn cứ. Không yêu cầu hoặc lưu chain-of-thought.
4. Phân biệt chưa thu thập, từ chối, chưa đủ bằng chứng và mức năng lực thấp có bằng chứng. Không biến từ chối thông tin tùy chọn thành điểm kém.
5. Câu hỏi của ứng viên, câu trả lời, source ID/version, trạng thái known/unknown/conflict/expired và việc recruiter cần trả lời. Trong dữ liệu, `known` tương ứng `FAQAnswer.status = answered`.
6. Cờ cần kiểm tra: STT không chắc, sửa thông tin, câu AI chưa xác nhận phát, phiên hết giờ hoặc provider lỗi.
7. Reviewer, thời điểm duyệt, ghi chú và trạng thái draft/reviewed; không có nhãn tự động “tuyển/loại”.

Dashboard cho phép mở turn gốc để đối chiếu, không chỉ thấy một điểm tổng. AI nói bị ngắt chỉ được lưu phần đã xác nhận phát; candidate turn dùng bản finalized. Nếu evidence không tồn tại hoặc không thuộc phiên, loại nhận định và gắn cờ thay vì bịa trích dẫn. Sửa dữ liệu sau phiên làm input version mới, đánh dấu bản cũ đã bị thay thế và yêu cầu duyệt lại.

## Job DB bền vững, không cần queue riêng

Khi kết thúc phiên, cùng transaction ghi status cuối và tạo `ReportJob` với unique key `(session_id, input_version)`. Với phiên chết trước khi kết thúc, cơ chế đối soát phiên stale phải ghi kết thúc gián đoạn và bảo đảm tạo job còn thiếu.

End interview hiệu lực ngay mọi pha, dừng media/cancel output không confirm/forced spoken wrap; về Roles với inline “Interview ended”, không hứa xóa. Offline dừng local và reconcile terminal/stale-session cleanup, không resume media. Interview UI chỉ robot stage + đúng ba controls mic/speaker/End, không timer; deadline/delivery/connection vẫn backend.

Worker poll job pending hoặc lease hết hạn; claim nguyên tử bằng row lock/lease, tăng attempts và có lease_until. Chỉ worker đang giữ lease hợp lệ được hoàn tất. Gọi model ngoài transaction dài; validate output và evidence, rồi ghi report + chuyển job done trong transaction. Unique key cho report bảo vệ khỏi chạy trùng, kể cả worker chết sau khi gọi model. Retry có thể tốn thêm tiền model nhưng không tạo hai báo cáo hiệu lực cho cùng input.

Lỗi tạm thời retry với backoff hữu hạn; lỗi hết số lần chuyển failed, hiển thị cho operator và cho phép retry có kiểm soát. Lease quá hạn được nhận lại; job mới không ghi đè report của input version khác. Trạng thái pending/processing/failed phải hiển thị rõ cho recruiter, không giả vờ có kết quả.

FastAPI `BackgroundTasks` không phải cơ chế durable và không được dùng làm bảo đảm duy nhất. Kiểm chứng bằng cách dừng worker giữa claim/model/write rồi khởi động lại; kiểm tra báo cáo duy nhất, không mất job và không dùng transcript chưa finalized.

## Quyền và lưu trữ

Chỉ người được phân quyền theo chiến dịch xem/duyệt báo cáo; audit việc truy cập/sửa/duyệt. Transcript/report/room CV cần retention riêng; không giữ report vô hạn. CV URL chỉ assigned HR/worker khi cần, không candidate mặc định. Xóa gồm room/CV copies/objects/cache và backup theo policy; job/restore kiểm tra tombstone trước publish, không hồi sinh dữ liệu. Demo cũng áp dụng quyền/xóa, ưu tiên synthetic. Chủ sở hữu chốt pháp lý, consent phiên, HR notice trước upload và giới hạn backup trước dữ liệu thật.
