# Checklist triển khai MVP theo vai trò

Đây là công việc dự kiến; chỉ đánh dấu phần có kết quả kiểm tra. Skeleton local đã được kiểm tra trong phạm vi ghi bên dưới, không phải nghiệm thu MVP. Dùng cùng [yêu cầu sản phẩm](../business/requirements.md), [kiến trúc](../architecture/system-architecture.md), [luồng hội thoại](../architecture/conversation-workflow.md) và [kế hoạch kiểm chứng](validation-plan.md).

Thứ tự chung: chốt nghiệp vụ và hợp đồng → dựng khung chạy local → kiểm tra luồng text → thêm voice → demo nội bộ. Các vai trò có thể làm song song sau khi chốt hợp đồng dữ liệu và API.

Phạm vi UI đúng [7 page types](../product/README.md): Home, Sign in, Roles, Join room, Interview, HR, Admin; một desktop 1440 frame mỗi loại. Mobile/tablet/responsive OUT OF SCOPE, kiểm tra desktop browsers/keyboard/focus/contrast/zoom. Không candidate profile/CV upload/change/share/version/history/settings portal. Recording/export ngoài active MVP, không disabled controls. Machine-derived profile artifact không là portal.

## BA

- [ ] Chốt phạm vi MVP và phần không làm; xác nhận AI chỉ hỗ trợ, không tự quyết định tuyển dụng.
- [ ] Chuẩn bị JD, tiêu chí sàng lọc và mục tiêu cho một chiến dịch mẫu.
- [ ] Chốt bộ câu hỏi lõi và rubric dùng chung; nêu rõ bằng chứng cần có cho từng tiêu chí.
- [ ] Chốt các pha, ngân sách thời gian, giới hạn followup và giới hạn làm rõ STT riêng.
- [ ] Chuẩn bị FAQ từ nguồn nội bộ được phép dùng, có người duyệt và thời hạn hiệu lực.
- [ ] Chốt quy trình recruiter duyệt JD, câu hỏi, rubric và FAQ; thay đổi tạo phiên bản mới, không sửa phiên bản đã khóa của phiên đang chạy.
- [ ] Chốt 7 trang: Home chỉ navbar/hero hai CTA/static robot preview (không badge/Example chip/speaking/disclaimer); Join room gộp consent/mic/speaker/waiting/errors; Interview chỉ stage + đúng ba controls mic/speaker/End; HR Campaigns/Rooms/Reports tabs, Admin grants/health; policies/contacts inline/dialog trước consent, không trang/frame phụ.
- [ ] Chốt trường cần thu và lý do; mặc định trường nhạy cảm là tùy chọn, không hỏi dữ liệu không cần thiết và không chấm điểm tuổi.
- [ ] Soạn thông báo AI/mục đích/consent phiên-transcript-report và quyền dừng; HR authority/lawful basis/notice riêng trước CV upload, không dùng consent candidate về sau hồi tố; missing CV “No CV attached” không chặn.
- [ ] Chốt thời hạn lưu, quyền xem, xóa và cách xử lý bản sao trong backup cho từng loại dữ liệu.
- [ ] Chốt hành vi skip, sửa câu trả lời, từ chối cung cấp thông tin và kết thúc sớm; không suy ra năng lực thấp từ dữ liệu thiếu.
- [ ] Duyệt guardrail: không lộ dữ liệu/secret, không bịa FAQ, không hứa liên hệ hoặc vòng sau khi thiếu căn cứ; không ép candidate im lặng theo pha.
- [ ] Chốt mẫu báo cáo có bằng chứng theo turn, trạng thái thiếu dữ liệu và bước người tuyển dụng duyệt kết quả.
- [ ] Chuẩn bị ví dụ synthetic cho luồng bình thường và các case lỗi/policy; thống nhất tiêu chí nghiệm thu với đội kỹ thuật.

## DevOps

- [ ] Chốt phiên bản Node.js, Python, PostgreSQL và cách quản lý phiên bản cùng Fullstack/AI Engineer.
- [ ] Phối hợp tạo `.env.example` chỉ có giá trị mẫu và `.gitignore` loại secret; provider key chỉ ở server/worker, không dùng tiền tố `NEXT_PUBLIC`.
- [ ] Tạo database và user PostgreSQL với quyền cần thiết; cấu hình volume bền vững và phối hợp Fullstack chạy migration.
  - [x] Local PostgreSQL 16.11 provisioning: app role non-admin, authenticated TCP checks, named volume; synthetic row survives restart and down/up (`tests/verify_compose.py`).
  - [x] Dev/test contract SQL slice and guarded fixture seed; real isolated PostgreSQL migration checksum/idempotence/rollback, selected constraints and restart persistence (`tests/verify_seed.py`).
  - [ ] Production migration upgrades, full schema/state/auth constraints, backup/restore and acceptance.
- [ ] Tạo cấu hình LiveKit Cloud, credential và kết nối mạng cho API/worker/browser; không tự host media khi chưa có nhu cầu.
- [x] Viết Dockerfile cho web Next.js, API FastAPI và worker dài hạn; explicit COPY, multi-stage, nonroot and runtime export checks passed locally.
- [x] Viết `.dockerignore` để không đưa secret, cache và file không cần thiết vào build context; deny-by-default allowlist.
- [x] Viết `docker-compose.yml` cho web/api/worker/postgres với env, loopback ports, network và named volume rõ ràng; LiveKit vẫn Cloud, chưa kết nối.
- [x] Local health/readiness: authenticated DB SELECT 1, API `/ready`, web HTTP, worker idle PID heartbeat; API/worker wait for healthy DB. Not provider/job readiness.
- [x] README startup/rebuild/private log/down guide; ordinary down preserves volume, destructive cleanup only for owned synthetic test.
- [ ] Thiết lập CI chạy lint, build và check phù hợp; phối hợp kiểm tra migration trên database thử trước khi triển khai.
- [ ] Cấu hình HTTPS/domain, CORS giới hạn origin và đường kết nối media; kiểm tra quyền mic trên browser mục tiêu.
- [ ] Triển khai worker như tiến trình dài hạn, có restart và shutdown phù hợp; phối hợp kiểm tra phục hồi job với AI Engineer.
- [ ] Thiết lập backup PostgreSQL và thực hành restore; kiểm tra chính sách retention/xóa cùng Fullstack.
- [ ] Theo dõi health, lỗi provider, job backlog và chi phí tối thiểu; log ID giả danh, không log token hay nội dung cá nhân đầy đủ.
- [ ] Provision private object store + quarantine/scanner cho HR room CV retained NGAY; secrets server-only, assigned HR/worker scoped URLs TTL ngắn, retention/xóa/copies/backups/tombstones; không scan không publish room chứa file. Không thêm Redis/Kafka/Kubernetes.

## Fullstack Developer

- [x] Khởi tạo Next.js với TypeScript và FastAPI; tạo cấu trúc tối thiểu cho web, API và mã dùng chung cần thiết. Verified by isolated production build/typecheck, Home HTTP and independent API HTTP (`tests/verify_local.py`).
  - [x] Home desktop: Tailwind v4/PostCSS, 56 px navbar/30 px logo/compact Sign in, two hero CTAs and user-trimmed static robot preview; no badge/Example chip/speaking/disclaimer.
  - [x] FastAPI `/health` liveness without provider credentials.
  - [x] Idle worker startup, fake config check and SIGTERM shutdown (`tests/test_backend.py`); no LiveKit jobs yet.
  - [x] Python-only credential validation and FAKE-secret public bundle/HTML scan; no real `.env` read during verification.
- [ ] Nối cấu hình env và PostgreSQL; phối hợp DevOps về `.env.example`, kết nối local và migration.
- [ ] Chốt API/Room/CVAttachment binding exact candidate + campaign + optional attachment ID/version/hash hoặc absence; server bounded PDF 5 MB configurable proposal, relationship/authority/scan validation; metadata guardrail không thêm FAQ status/action enum.
  - [x] [Technical v1 baseline](../architecture/api-data-contract.md), generated OpenAPI and typed synthetic fixtures validated offline; domain routes, actual CV upload/scanner and authorized policy approval remain open.
- [ ] Tạo migration cho campaign/FAQ version, session, consent, turns, facts/corrections, candidate questions/FAQ answers, report jobs và reports; có ràng buộc chống trùng.
  - [x] Isolated dev/test JSONB snapshot + relational reference slice, guarded seed, exact rerun/conflict rollback, selected FK/immutability/unique constraints verified on PostgreSQL (`tests/verify_seed.py`). Not full production write API or worker recovery.
- [ ] Làm auth và API kiểm tra quyền theo chiến dịch/phiên; candidate chỉ dùng phiên được cấp, operator không mặc nhiên đọc mọi nội dung.
- [ ] Làm HR Campaigns tab tạo JD/đề xuất/approval/lock; Rooms tab tạo identity/campaign/schedule/optional HR CV và Publish invitation. Draft sửa được; publish/invite khóa binding kể cả absence; sai CV sau đó revoke/cancel + NEW room, không swap ongoing history. CV chỉ HR reference, không parse/score/prompt/evidence.
- [ ] Làm Google sign-in không first-profile wizard, Roles assigned rooms embedded và Join room gộp notice/consent/devices/waiting/access errors; lưu notice/time/choice trước media, HR contact inline cho mismatch, không candidate CV download mặc định.
- [ ] Làm kiểm tra mic sau consent phù hợp và API cấp LiveKit token TTL ngắn, đúng room/identity/quyền; kiểm tra lại quyền khi cấp mới.
- [ ] Tích hợp LiveKit: Interview chỉ robot stage + mic mute/unmute, speaker mute/unmute, End interview; status/error ngắn trong stage, không navbar/timer/volume/captions/extra controls. Website English, speech/evidence Vietnamese.
- [ ] Reconnect/refresh đúng phiên/quyền, không replay/duplicate; End ngay mọi pha dừng capture/playback/cancel output không confirm/forced wrap, trả Roles inline “Interview ended”, không hứa xóa; offline reconcile terminal, không tự resume audio.
- [ ] Làm API lưu finalized turns và correction có provenance; phối hợp worker về delivery tracking, không coi partial là bằng chứng cuối.
- [ ] Phối hợp AI Engineer kết thúc phiên và tạo report job bền vững trong DB; transaction và khóa duy nhất ngăn mất job hoặc báo cáo trùng khi retry.
- [ ] Làm Reports tab + inline detail/drawer xem transcript/FAQ sources/report/evidence/review, pending/failed/retry; Admin một workspace users/HR grants + service health và expandable audit metadata, không config/content default access.
- [ ] Thực hiện retention/quyền/xóa room/CV/transcript/report và copies/backups theo policy; job/scan/restore không hồi sinh tombstone. Recording/export future OUT OF SCOPE, không triển khai active MVP.
- [ ] Xử lý mic denied, timeout, mất mạng và lỗi báo cáo; hướng dẫn thử lại/dừng, không hiển thị lỗi như kết quả hoàn tất.
- [ ] Kiểm tra tích hợp luồng bình thường, từ chối consent, token hết hạn và truy cập chéo chiến dịch; phối hợp kiểm tra text trước voice.

## AI Engineer

- [x] Partial local text verification: shared bounded controller, synthetic cases and 20/20 offline artifacts; see [scope/results](../ai/verification-results.md). The first live writer failed; the separately authorized second run below records technical success only. Provider quality, human listening, integration and all broader items below remain open.

- [ ] Cài LiveKit Agents Python và plugin tương thích; chốt phiên bản với DevOps, giữ worker chạy dài hạn.
- [ ] Cấu hình STT phía server với baseline Deepgram Nova-3, `vi`; xác minh hỗ trợ tiếng Việt, streaming, quota và vùng hiện hành.
- [ ] Cấu hình LLM phía server bằng Gemini Flash còn được hỗ trợ; xác minh model ID, region, quota và plugin trước khi dùng.
- [ ] Cấu hình TTS phía server bằng ElevenLabs với voice tiếng Việt; baseline `eleven_flash_v2_5` cần xác minh khả dụng và hỗ trợ thực tế.
- [ ] Thử từng provider bằng dữ liệu synthetic, sau đó nối STT → LLM → TTS; không coi tên baseline là bằng chứng đã hoạt động.
  - [x] Direct-HTTPS functional evidence `20261107T130859Z-0d96004c`: ElevenLabs `eleven_flash_v2_5` generated three 24 kHz mono 16-bit WAVs with actual default voice `hpp4J3VqNfWAUOO0d1Us`; Deepgram `nova-3`/`vi` returned three batch transcripts; Gemini `gemini-3.5-flash-lite` returned two schema-valid, policy-accepted expected proposals. [Exact scope and observations](../ai/verification-results.md#second-authorized-live-run--technical-functional-success-not-quality-approval).
  - [ ] Human listening, approved WER/Vietnamese quality, plugin streaming and full pipeline remain pending; name round-trip WER 44.44%, numbers/negation 0%, no approved threshold. Report model not tested.
- [ ] Làm luồng text với campaign snapshot đã duyệt, câu hỏi lõi và schema quyết định theo hợp đồng đã chốt.
- [ ] Làm controller kiểm tra action, criterion/evidence ID, thứ tự pha, deadline và giới hạn followup/làm rõ; quyết định sai phải fallback an toàn.
- [ ] Xử lý skip, clarify, correction và end; lưu trạng thái cùng Fullstack để không chỉ giữ trong RAM, không tự điền dữ liệu thiếu.
- [ ] Nạp FAQ nhỏ từ nguồn đã duyệt đúng phiên bản/hiệu lực; thiếu, mâu thuẫn hoặc hết hạn thì ghi recruiter followup, không tìm web hay bịa đáp án.
- [ ] Kiểm tra guardrail trên cả câu hỏi sinh trước phiên và followup: chống injection, không hỏi sâu dữ liệu nhạy cảm, không lộ secret hoặc hứa vòng sau thiếu căn cứ.
- [ ] Kiểm tra ý nghĩa lời nói ngoài schema; diễn đạt từ hành động/nguồn được phép, từ chối ngắn có lý do, cho phép tiếp tục hoặc dừng.
- [ ] Phân biệt partial/final STT, xác nhận tên/số/phủ định khi cần; persist turn cuối và correction có liên kết, report chỉ dùng dữ liệu cuối có căn cứ.
- [ ] Làm ngắt lời: hủy LLM/TTS, xóa audio chờ và loại chunk trễ bằng generation ID; phối hợp client kiểm chứng phần thực sự đã phát.
- [ ] Lưu delivery status và chỉ dùng phần assistant xác nhận đã phát làm bằng chứng; nếu không xác nhận được thì đánh dấu và hỏi lại ngắn.
- [ ] Làm worker báo cáo nhận job DB có lease/retry và chống trùng; kiểm tra restart, evidence turn, correction và trạng thái thiếu dữ liệu, không đưa quyết định tuyển tự động.
- [ ] Thử giọng Bắc/Trung/Nam, Việt–Anh, nhiễu, echo, ngập ngừng, timeout/quota và retry hữu hạn; đo latency đến âm thanh đầu tiên và chi phí thực gồm retry, ghi cấu hình/cỡ mẫu thay vì hứa SLA.

## Tích hợp và hoàn tất demo nội bộ

- [ ] Cùng kiểm tra luồng text với dữ liệu synthetic, nguồn được duyệt và đầy đủ case policy trong kế hoạch kiểm chứng trước khi thêm voice.
- [ ] Chạy voice trên browser/mạng mục tiêu; kiểm tra consent, ngắt lời, sửa thông tin, reconnect và dừng, rồi đối chiếu transcript với phần đã nghe.
- [ ] Thử restart/retry job, quyền truy cập âm tính, retention/xóa và restore; recruiter kiểm tra evidence và duyệt tính hữu ích của báo cáo.
- [ ] Ghi kết quả, lỗi còn mở, cấu hình provider/SDK và chi phí đo được; chỉ đánh dấu hoàn tất phần đã có bằng chứng, không xem demo là sẵn sàng dùng thật.
