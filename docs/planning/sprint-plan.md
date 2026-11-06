# Kế hoạch MVP theo sprint

Đây là kế hoạch đề xuất, chưa triển khai và chưa có kết quả nghiệm thu. **Toàn bộ task bên dưới: dự kiến, chưa hoàn thành.** Tài liệu bổ sung, không thay [checklist theo vai trò](implementation-checklist.md). Phạm vi theo [yêu cầu R01–R15](../business/requirements.md), [kiến trúc](../architecture/system-architecture.md), [hội thoại](../architecture/conversation-workflow.md), [I/O](../architecture/io-contracts.md), [artifact](../architecture/data-artifacts.md) và [báo cáo](../report/interview-report.md).

## Cách dùng và phụ thuộc

- Đội tự chọn độ dài sprint sau khi biết năng lực và đầu vào; không suy ra ngày giao, giờ công, story point, velocity, nhân sự hoặc chi phí từ kế hoạch này.
- Thứ tự là đề xuất. Vai trò có thể làm song song khi đủ đầu vào; task có phụ thuộc chỉ bắt đầu tích hợp sau khi đầu ra trước được duyệt. Không qua cổng thì chặn tích hợp giai đoạn kế tiếp, không che lỗi bằng đổi trạng thái hoàn tất.
- Người duyệt hiện được gọi theo vai trò; phải gán cá nhân thực trước nghiệm thu. BA điều phối quyết định nghiệp vụ, recruiter duyệt nội dung/tính hữu ích, người phụ trách kỹ thuật duyệt hợp đồng và tích hợp, operator duyệt vận hành. BA không thay người có thẩm quyền về riêng tư/pháp lý.
- Không thêm Redis, Kafka, Kubernetes, vector DB, PSTN, Gemini Live hoặc web search chính sách. Sản phẩm vẫn là browser voice; harness text chỉ dùng kiểm chứng, không phải tính năng text fallback.

| Sprint | Mục tiêu / đường phụ thuộc chính | Người duyệt cổng |
| --- | --- | --- |
| 0 | Nghiệp vụ → quyền/consent → hợp đồng → bộ case | Recruiter + người phụ trách kỹ thuật + chủ sở hữu riêng tư |
| 1 | Hợp đồng → web/API/worker + DB + môi trường/provider + cách chạy | Người phụ trách kỹ thuật + operator |
| 2 | Nền tảng → campaign khóa + phiên có quyền → controller text + harness | Recruiter + người phụ trách kỹ thuật; chưa phải cổng text đầy đủ |
| 3 | Transcript có version → job/report/review → cổng mô phỏng text | Recruiter + người phụ trách kỹ thuật |
| 4 | Cổng text → browser media + pipeline → interruption/recovery → cổng audio | Recruiter/người duyệt tiếng Việt + người phụ trách kỹ thuật |
| 5 | Cổng audio → deploy + vận hành/xóa/restore → UAT demo | Recruiter + operator + chủ sở hữu riêng tư |

ID task ổn định dạng `S0-01`; mục “Tiền đề” là cạnh phụ thuộc bắt buộc. Cổng từng sprint là điều kiện bổ sung cho các cạnh task.

Giữ nguyên 24 task IDs/checkboxes. UI đúng [7 page types](../product/README.md): Home `/`, Sign in `/login`, Roles `/roles`, Join room `/rooms/{id}`, Interview `/sessions/{id}/interview`, HR `/hr`, Admin `/admin`, một desktop frame 1440 mỗi loại. Mobile/tablet/responsive OUT OF SCOPE; kiểm tra desktop browsers, keyboard/focus/contrast/zoom. Không candidate profile/CV upload/change/share/version/history/settings portal. Recording/export future OUT OF SCOPE, không disabled controls; machine-derived profile artifact không là portal.

## Definition of Done chung

- Đầu ra được lưu và có phiên bản; phạm vi thay đổi, cấu hình, cách kiểm tra và lỗi còn mở được ghi rõ. Không đánh dấu xong chỉ vì có code hoặc container đang chạy.
- Có bằng chứng happy path và lỗi quan trọng tương ứng; dùng synthetic data, không đưa secret/PII đầy đủ vào log, commit hay browser. Kiểm tra quyền âm tính cho mọi bề mặt dữ liệu mới.
- Đối chiếu R01–R15 và ma trận [kiểm chứng](validation-plan.md), gồm ý nghĩa lời nói chứ không chỉ schema. Policy baseline: không vi phạm trong tập case đã duyệt, không phải bảo đảm tuyệt đối.
- Người duyệt theo vai trò xác nhận đầu ra và tiêu chí; điều kiện chưa chốt phải có quyết định được duyệt trước tích hợp. Ghi giới hạn, không tuyên bố production-ready hoặc SLA/chi phí chưa đo.

## Sprint 0 — Chốt đầu vào và hợp đồng

**Mục tiêu:** biến các điểm mở thành đầu vào có thể xây và kiểm tra.

- [ ] **S0-01 — Campaign mẫu và hành trình nghiệp vụ**
- **Vai trò chính:** BA; phối hợp recruiter, AI Engineer, Fullstack Developer.
- **Tiền đề:** yêu cầu R01–R15 và checklist hiện tại.
- **Phạm vi:**
  - Chốt đúng 7 trang/quyền; Home chỉ navbar/hero hai CTA/Example preview; Join room gộp consent/devices/waiting/errors; Interview chỉ stage + ba controls mic/speaker/End; HR 3 tabs, Admin grants/health/audit metadata inline. Policies/contacts readable inline/dialog, không extra frames.
  - Chuẩn bị JD synthetic, mục tiêu sàng lọc, câu hỏi lõi, criterion IDs và rubric có ví dụ bằng chứng.
  - Chốt pha, time budget, followup và clarification riêng; quy trình duyệt/khóa và tạo version mới.
  - Chuẩn bị FAQ nhỏ có source/version, người duyệt và hiệu lực; mẫu báo cáo với bước người tuyển dụng duyệt.
- **Đầu ra:** gói campaign mẫu và sơ đồ hành trình được version hóa.
- **Nghiệm thu:** recruiter duyệt từng câu/rubric/FAQ; mỗi tiêu chí có cách nhận diện đủ/thiếu bằng chứng; không có hành động tự tuyển/loại; thay đổi không sửa version đã khóa.

- [ ] **S0-02 — Consent, dữ liệu tối thiểu và lời guardrail**
- **Vai trò chính:** BA; phối hợp chủ sở hữu riêng tư/pháp lý, recruiter, AI Engineer.
- **Tiền đề:** S0-01.
- **Phạm vi:**
  - Liệt kê trường cần thu, lý do, bắt buộc/tùy chọn; tuổi tắt mặc định, không chấm tuổi, không DOB/địa chỉ chính xác.
  - Soạn notice/consent phiên-transcript-report và quyền dừng; HR authority/lawful basis/notice riêng trước upload CV, không consent candidate hồi tố; “No CV attached” được phép, không candidate requirement.
  - Chốt quyền xem/sửa/xóa, retention từng loại, provider copies và giới hạn backup/legal hold; chỉ định người xử lý yêu cầu.
  - Duyệt lời R12–R15: hạn chế tiết lộ khác thiếu nguồn; từ chối không bị phạt; tự kể nhạy cảm không bị hỏi sâu; không hứa xóa/liên hệ/vòng sau thiếu căn cứ.
- **Đầu ra:** policy/consent version và danh mục dữ liệu phê duyệt; recording/export ngoài active MVP.
- **Nghiệm thu:** ký duyệt trước thu dữ liệu, HR lawful basis trước CV upload; từ chối consent phiên dừng trước media; CV optional không chặn eligibility; mọi loại dữ liệu có quyền/retention rõ.

- [ ] **S0-03 — Chốt API, event, state và version dữ liệu**
- **Vai trò chính:** Fullstack Developer; phối hợp AI Engineer, BA, DevOps.
- **Tiền đề:** S0-01, S0-02.
- **Phạm vi:**
  - Chốt endpoint/auth/error, loại ID, payload/context limits, TTL token, sequence/dedupe, transaction và state transitions; tách phase khỏi active/interrupted/ended.
  - Định nghĩa schema campaign/FAQ, Room/CVAttachment, session/consent, turns/facts/corrections/questions/answers/jobs/reports. Room binds exact identity + campaign + optional CV ID/version/hash hoặc absence; publish/invite khóa, sai CV sau đó revoke/cancel + NEW room. Server relationship/PDF validation, 5 MB configurable proposal, quarantine/scan trước publish; không scan không publish room chứa file. Không parse/score/prompt CV; metadata không là candidate turn.
  - Chốt transcript source/input version, snapshot bất biến, provenance/model/config version, correction và duyệt lại report; planned/partial/unknown không là evidence.
  - Giải quyết cách lưu metadata lý do từ chối/trì hoãn và ánh xạ vào action hiện có; giữ FAQ status answered/unknown/conflict/expired, không thêm FAQ/action enum, không dùng unknown che hạn chế tiết lộ.
  - Chốt giao thức generation/delivery và fallback unknown; budget retry/reconnect/clarification, stale session, tombstone và quyền publish job.
- **Đầu ra:** hợp đồng triển khai có ví dụ hợp lệ/không hợp lệ và quyết định các điểm mở trong I/O/artifact/report.
- **Nghiệm thu:** Fullstack và AI Engineer đối chiếu cùng fixture; mọi luồng từ consent đến report có owner/đầu vào/đầu ra; không còn ánh xạ guardrail chưa giải quyết; người phụ trách kỹ thuật duyệt constraints và version semantics.

- [ ] **S0-04 — Bộ case và ngưỡng chất lượng được duyệt**
- **Vai trò chính:** BA; phối hợp AI Engineer, Fullstack Developer, recruiter/người duyệt tiếng Việt.
- **Tiền đề:** S0-01, S0-02, S0-03.
- **Phạm vi:**
  - Tạo fixture synthetic cho happy path, skip/refusal/correction/end, FAQ và toàn bộ case R12–R15 trong kế hoạch kiểm chứng.
  - Tạo tình huống sai quyền, token hết hạn, worker chết, duplicate event, thiếu consent, deadline và provider lỗi.
  - Chốt desktop browser/mạng, 7-frame inventory, stage/3 controls/End, optional missing CV và wrong-CV/scan/permission edges; nhóm giọng Bắc/Trung/Nam, Việt–Anh, nhiễu/echo, entity/phủ định.
  - Thống nhất ngưỡng chấp nhận chất lượng, cỡ mẫu và cách đo latency/cost; tách mục tiêu dự kiến khỏi số đo, không tự đặt SLA.
- **Đầu ra:** test matrix có expected outcome, evidence cần giữ và người duyệt từng nhóm.
- **Nghiệm thu:** mọi dòng ma trận validation có case/owner; ngưỡng và budget cần thiết được ký duyệt trước dùng làm pass/fail; policy yêu cầu không vi phạm trong tập đã duyệt; chỉ số chưa đo mang nhãn chưa đo.

**Exit gate:** bốn đầu ra được duyệt, đặc biệt consent, metadata guardrail và snapshot/version; điểm chưa chốt chặn tích hợp phụ thuộc, không chuyển thành giả định ngầm.

## Sprint 1 — Nền tảng chạy được và kiểm tra provider sớm

**Mục tiêu:** môi trường local có DB bền vững, secret đúng chỗ và cấu hình có thể tái lập.

- [ ] **S1-01 — Khung web, API và worker**
- **Vai trò chính:** Fullstack Developer; phối hợp AI Engineer, DevOps.
- **Tiền đề:** S0-03.
- **Phạm vi:**
  - Chốt phiên bản Node.js/Python/PostgreSQL và quản lý dependency cùng đội.
  - Dựng Next.js TypeScript, FastAPI và cấu trúc Python agent worker dài hạn tối thiểu.
  - Tách cấu hình browser/server/worker; tạo .env.example chỉ giá trị mẫu, .gitignore loại secret.
- **Đầu ra:** skeleton và hướng dẫn cấu hình môi trường.
- **Nghiệm thu:** web/API/worker khởi động độc lập bằng cấu hình mẫu phù hợp; thiếu env bắt buộc báo lỗi rõ; không provider key mang tiền tố NEXT_PUBLIC hoặc xuất hiện trong browser bundle/log.

- [ ] **S1-02 — PostgreSQL và migration nguồn chuẩn**
- **Vai trò chính:** Fullstack Developer; phối hợp DevOps, AI Engineer.
- **Tiền đề:** S1-01, S0-03.
- **Phạm vi:**
  - Tạo DB/user với quyền cần thiết, volume bền vững và migration cho toàn bộ thực thể đã chốt.
  - Thêm foreign keys, ràng buộc version, event/turn dedupe, unique job/report và audit refs theo hợp đồng.
  - Áp migration trên DB thử, seed synthetic và kiểm tra transaction turn + state; chuẩn bị rollback/phục hồi an toàn.
- **Đầu ra:** migrations, seed và quy trình kiểm tra DB.
- **Nghiệm thu:** DB mới migrate thành công; duplicate event/job bị ngăn; ref sai phiên/version bị từ chối theo hợp đồng; restart dịch vụ giữ dữ liệu; user ứng dụng không có quyền quản trị không cần thiết.

- [ ] **S1-03 — LiveKit Cloud và smoke provider phía server**
- **Vai trò chính:** AI Engineer; phối hợp DevOps, Fullstack Developer.
- **Tiền đề:** S1-01, S0-02, S0-04.
- **Phạm vi:**
  - Thiết lập credential/network LiveKit Cloud, backend provider env và LiveKit Agents Python/plugins tương thích; không tự host media.
  - Smoke từng provider bằng synthetic: Deepgram Nova-3 vi streaming, Gemini Flash còn được hỗ trợ, ElevenLabs voice tiếng Việt; xác minh baseline eleven_flash_v2_5 thực tế.
  - Ghi model/voice/region/quota/SDK/plugin, quyền dữ liệu và lỗi availability; thay baseline không khả dụng chỉ sau quyết định kỹ thuật được ghi nhận.
- **Đầu ra:** cấu hình server/worker và biên bản smoke, không chứa secret.
- **Nghiệm thu:** từng provider trả đầu ra hợp lệ trên mẫu hoặc có blocker rõ chặn voice; hỗ trợ tiếng Việt/streaming không được suy từ tên model; credential không vào browser/commit/log.

- [ ] **S1-04 — Container, readiness, CI và hướng dẫn local**
- **Vai trò chính:** DevOps; phối hợp Fullstack Developer, AI Engineer.
- **Tiền đề:** S1-01, S1-02, S1-03.
- **Phạm vi:**
  - Viết Dockerfile web/API/worker và .dockerignore; có thể dùng chung image Python cho API/worker.
  - Compose web/api/worker/postgres với env, ports, network, volume; LiveKit vẫn Cloud; health/readiness và chờ DB thực sự sẵn sàng.
  - CI lint/build/check phù hợp và migration trên DB thử; ghi cách startup/rebuild/log/down không xóa volume thường lệ.
  - Provision private CV object store/quarantine/scanner và secret server-only; scoped URL assigned HR/worker khi cần, không candidate mặc định, không chờ recording/export. Scan fail/unavailable chặn publish room có file, metadata/hash/version immutable; retention/backups/tombstone có owner.
- **Đầu ra:** cấu hình chạy local, CI và startup guide.
- **Nghiệm thu:** làm theo guide dựng được môi trường sạch; DB chưa sẵn sàng không báo ready giả; build context không chứa secret/cache; CI phát hiện build/migration lỗi; down thông thường không mất dữ liệu.

**Exit gate:** local có thể tái lập, migration và readiness có bằng chứng; provider blocker phải được giải quyết trước tích hợp voice, không coi smoke riêng lẻ là pipeline đã hoạt động.

## Sprint 2 — Campaign và controller qua mô phỏng text

**Mục tiêu:** kiểm tra nghiệp vụ và persistence trước khi nối audio.

- [ ] **S2-01 — Tạo, sinh đề xuất và khóa campaign**
- **Vai trò chính:** Fullstack Developer; phối hợp AI Engineer, BA, recruiter.
- **Tiền đề:** S1-02, S1-04, S0-01.
- **Phạm vi:**
  - Làm Campaigns tab trong `/hr`, form inline/drawer JD bounded/AI đề xuất theo rubric, không frame editor riêng; JD là dữ liệu không tin cậy.
  - Cho recruiter duyệt câu hỏi/rubric/FAQ, chặn câu nhạy cảm không cần thiết ngay từ sinh đề xuất.
  - Khóa snapshot, thay đổi tạo version mới; kiểm tra quyền chỉnh sửa theo campaign.
- **Đầu ra:** luồng campaign có approval và immutable version.
- **Nghiệm thu:** campaign chưa duyệt không mở phiên; injection trong JD không đổi policy; câu cấm bị chặn trước dùng; phiên cũ vẫn dùng version khóa sau khi tạo bản mới.

- [ ] **S2-02 — Invitation, quyền phiên và consent UI**
- **Vai trò chính:** Fullstack Developer; phối hợp BA, DevOps.
- **Tiền đề:** S2-01, S0-02, S0-03.
- **Phạm vi:**
  - Làm Rooms tab tạo identity/campaign/schedule/optional HR CV + Publish invitation với authority/relationship/scan gates; draft correction được, publish khóa binding/absence, sai file sau đó revoke/cancel + room mới. Google sign-in đơn giản, Roles assigned rooms embedded; auth scoped, operator metadata only.
  - Join room gộp notice/consent/mic/speaker/waiting/access errors; lưu version/time/choice, không media trước consent; HR contact inline cho CV mismatch, không candidate upload/download portal.
  - Admin `/admin` tối thiểu users/invite HR grants scoped + service/job status và expandable audit metadata, không settings/config browser/content default access; account/logout menu duy nhất, HR/Admin theo permission.
  - Tạo stage + đúng ba controls mic/speaker/End, status/errors trong stage; token LiveKit TTL ngắn đúng room/identity/quyền; refresh kiểm tra quyền lại, không timer/extra frames.
- **Đầu ra:** hành trình mời/consent và hợp đồng token thực thi.
- **Nghiệm thu:** từ chối consent không thu turn/media; không recording/export; missing CV hợp lệ nhưng scan fail/unavailable/wrong identity chặn publish file/room; binding publish bất biến; token hết hạn/sai scope bị từ chối, không secrets trong response.

- [ ] **S2-03 — Controller text và finalized persistence**
- **Vai trò chính:** AI Engineer; phối hợp Fullstack Developer.
- **Tiền đề:** S2-01, S2-02, S0-03.
- **Phạm vi:**
  - Nạp snapshot duyệt, sinh structured decision; controller kiểm tra action/criterion/evidence refs, thứ tự pha, deadline và hai loại hạn mức.
  - Thực thi skip/clarify/correction/end với safe fallback; persist state và finalized turns trong transaction, không chỉ RAM.
  - Lưu facts với null/status, correction liên kết gốc và provenance; loại partial/planned khỏi evidence, chưa hỏi không thành không đạt.
- **Đầu ra:** controller và adapter text synthetic dùng cùng logic sản phẩm.
- **Nghiệm thu:** đề xuất sai schema/ref/giới hạn bị chặn; deadline về wrap, end có hiệu lực mọi pha; restart đọc lại state đúng; retry không nhân turn; refusal không thành điểm thấp.

- [ ] **S2-04 — FAQ/guardrail và harness text**
- **Vai trò chính:** AI Engineer; phối hợp BA, Fullstack Developer, người duyệt tiếng Việt.
- **Tiền đề:** S2-03, S0-04.
- **Phạm vi:**
  - Nạp FAQ bounded đã duyệt đúng version/hiệu lực; lưu CandidateQuestion/FAQAnswer/source refs và recruiter followup.
  - Áp metadata guardrail đã chốt trước phát lời; kiểm tra nội dung cả core/followup và lời diễn đạt, không chỉ schema.
  - Chạy harness synthetic không cần report UI: FAQ known/unknown/conflict/expired, disclosure, nhạy cảm, hỏi sớm và hứa vòng sau.
  - Cho phép hỏi sớm: trả lời có nguồn hoặc xin phép trì hoãn; nếu không đồng ý vẫn xử lý; từ chối ngắn có lý do và lựa chọn tiếp tục/dừng.
- **Đầu ra:** harness tái chạy và transcript/decision/source traces ban đầu.
- **Nghiệm thu:** không lộ secret/context mật, không web search; chỉ defer vòng sau khi nguồn hợp lệ xác nhận và nói có điều kiện được mời; thiếu nguồn không hứa liên hệ/lịch; FAQ/action enum không đổi; người duyệt tiếng Việt xác nhận không trách móc/lặp vô hạn.

**Exit gate:** luồng consent → text → finalized state hoạt động trên mẫu và lỗi bắt buộc; report chưa hoàn chỉnh được ghi rõ. Chưa cho tích hợp voice trước cổng text đầy đủ ở sprint 3.

## Sprint 3 — Báo cáo bền vững và cổng text đầy đủ

**Mục tiêu:** có report có evidence, người duyệt và bằng chứng phục hồi job.

- [ ] **S3-01 — Kết thúc phiên, snapshot và durable report job**
- **Vai trò chính:** Fullstack Developer; phối hợp AI Engineer.
- **Tiền đề:** S2-03, S1-02.
- **Phạm vi:**
  - Cùng transaction ghi trạng thái cuối và ReportJob unique theo session/input_version; đối soát phiên stale thành interrupted và bổ sung job thiếu.
  - Dựng snapshot finalized turns/corrections cùng campaign/rubric/FAQ/config versions; correction sau phiên tạo input mới, không ghi đè report cũ.
  - Claim job nguyên tử bằng lease/row lock; định nghĩa attempts/backoff hữu hạn, failed và retry có kiểm soát.
- **Đầu ra:** vòng đời job DB và snapshot versioned.
- **Nghiệm thu:** crash giữa kết thúc phiên/tạo job không mất job; hai worker không claim hiệu lực đồng thời; source sửa tạo input mới; pending/failed không giả done; không dùng BackgroundTasks làm bảo đảm durable duy nhất.

- [ ] **S3-02 — Worker sinh report và kiểm tra evidence**
- **Vai trò chính:** AI Engineer; phối hợp Fullstack Developer, recruiter.
- **Tiền đề:** S3-01, S2-04.
- **Phạm vi:**
  - Gọi model ngoài transaction DB dài, validate report/evidence rồi commit report + job done chỉ khi lease còn hợp lệ.
  - Chỉ dùng finalized candidate turns đúng phiên/snapshot; đối chiếu câu đã hỏi bằng assistant confirmed delivery; correction mới nhất có căn cứ.
  - Phân biệt not_collected/refused/insufficient_evidence/supported; ghi self-report, phần thiếu, FAQ nguồn/followup và cờ lỗi; không hire/reject hay chain-of-thought.
- **Đầu ra:** report draft versioned và validator.
- **Nghiệm thu:** ref không tồn tại/sai phiên/partial bị loại và gắn cờ; từ chối nhạy cảm không giảm điểm; crash sau gọi model rồi retry chỉ có một report hiệu lực cho cùng input; worker lease cũ không publish được.

- [ ] **S3-03 — Recruiter review và quyền âm tính**
- **Vai trò chính:** Fullstack Developer; phối hợp BA, recruiter.
- **Tiền đề:** S3-02, S2-02.
- **Phạm vi:**
  - Làm Reports tab + inline detail/drawer trong `/hr` cho transcript/correction/report/evidence/FAQ versions/followup và pending/processing/failed; English summary/notes, nguyên văn Vietnamese evidence. Không report route/frame riêng hoặc CV làm evidence/prompt.
  - Lưu reviewer/time/note/status, audit quyền xem/sửa/duyệt; source mới đánh dấu superseded và yêu cầu duyệt lại.
  - Kiểm tra truy cập chéo campaign/session, operator không quyền nội dung, thao tác duyệt trái quyền và ref bị đoán.
- **Đầu ra:** UI review cùng bằng chứng kiểm tra quyền.
- **Nghiệm thu:** recruiter mở được turn gốc đúng snapshot; report lỗi không hiện hoàn tất; version mới không kế thừa duyệt cũ; tất cả truy cập âm tính trong bộ case bị từ chối và audit không lộ PII đầy đủ.

- [ ] **S3-04 — Cổng mô phỏng text và phục hồi**
- **Vai trò chính:** BA; phối hợp AI Engineer, Fullstack Developer, recruiter, DevOps.
- **Tiền đề:** S3-03, S0-04.
- **Phạm vi:**
  - Chạy toàn bộ nhóm text/policy của validation, cả injection speech/JD/context, disclosure dù có secret trong context và refusal lặp.
  - Kiểm tra sensitive refusal/tự kể, FAQ thiếu/mâu thuẫn/hết hạn, hỏi sớm và defer vòng sau có/không nguồn; xem ảnh hưởng report.
  - Dừng worker tại claim/model/write, lease hết hạn, xử lý trùng, stale session và corrections; giữ input/output/version/kết quả.
- **Đầu ra:** biên bản cổng text có transcript, report, evidence và lỗi mở.
- **Nghiệm thu:** mọi case policy bắt buộc pass, controller chặn hạn mức, nhận định có evidence hoặc thiếu dữ liệu rõ; restart không mất job/nhân report; recruiter ký duyệt. Case audio để sprint 4, không ghi pass thay.

**Exit gate:** đạt cổng mô phỏng text của validation; bất kỳ vi phạm policy hoặc lỗi durability chưa xử lý đều chặn tích hợp voice.

## Sprint 4 — Browser voice, ngắt lời và phục hồi media

**Mục tiêu:** giữ nguyên controller đã kiểm chứng khi thay đầu vào/đầu ra bằng audio thật.

- [ ] **S4-01 — Browser LiveKit sau consent**
- **Vai trò chính:** Fullstack Developer; phối hợp DevOps, AI Engineer.
- **Tiền đề:** S3-04, S2-02, S1-03.
- **Phạm vi:**
  - Nối LiveKit client mic/playback sau consent phù hợp; xác minh browser mục tiêu, autoplay và HTTPS cho môi trường thử.
  - Interview chỉ central robot stage + đúng ba controls mic mute/unmute, speaker mute/unmute, End interview; status/error ngắn trong stage. Mic permission/test speaker/hướng dẫn xử lý trước start ở Join room, không timer/captions/extra controls.
  - Nối token scoped/refresh với kiểm tra backend; không audio storage mặc định hoặc text fallback ngầm.
- **Đầu ra:** browser gửi mic và phát track đúng phiên.
- **Nghiệm thu:** không media trước consent, mic denied không thành hoàn tất, sai room/identity không join; đúng stage + 3 controls, không recording/export; browser không nhận secret, desktop keyboard/focus/contrast/zoom được kiểm tra.

- [ ] **S4-02 — STT → controller → LLM → TTS thực**
- **Vai trò chính:** AI Engineer; phối hợp Fullstack Developer, DevOps.
- **Tiền đề:** S4-01, S1-03, S2-04.
- **Phạm vi:**
  - Nối provider đã xác minh; decode/resample theo format từng chặng, không áp 16 kHz cho mọi provider.
  - Tách partial/final STT; xác nhận tên/số/phủ định khi cần và lưu correction; controller vẫn quyết định pha/quyền/hạn mức, LLM không điều khiển trực tiếp.
  - Giới hạn context, queue media và generation đang hoạt động; retry timeout/quota hữu hạn, báo gap/hỏi lại thay vì âm thầm bỏ candidate audio.
- **Đầu ra:** pipeline voice với cấu hình model/voice/plugin versioned.
- **Nghiệm thu:** mẫu synthetic đi đủ mic đến tiếng trả lời; partial không vào evidence; decision sai bị controller chặn như text; provider lỗi không tạo answer giả hoặc retry vô hạn; model/voice thực sự hỗ trợ tiếng Việt.

- [ ] **S4-03 — Interruption, delivery và reconnect**
- **Vai trò chính:** AI Engineer; phối hợp Fullstack Developer.
- **Tiền đề:** S4-02, S0-03.
- **Phạm vi:**
  - Barge-in hủy cả LLM/TTS, dừng/xóa audio chờ và loại chunk trễ bằng generation ID; kiểm tra noise/echo không gây lệnh giả.
  - Kiểm chứng playback acknowledgement/text mapping; chỉ canonicalize phần xác nhận phát. Không suy prefix từ tỷ lệ thời lượng; không map được thì unknown, hỏi lại ngắn khi phù hợp.
  - Reconnect đối soát sequence/turn đã commit, pending generation và timeline/gaps; refresh đúng quyền, không replay cũ/nhân phiên; deadline/end vẫn hiệu lực.
  - End intent ở mọi pha/reconnect/error dừng local mic/playback/cancel output ngay không confirm/forced wrap; backend terminal + report job idempotent, trả Roles inline “Interview ended”. Offline reconcile không tự resume media; không hứa xóa dữ liệu, deadline chỉ nội bộ.
- **Đầu ra:** delivery tracking và phục hồi phiên có trace.
- **Nghiệm thu:** chen giữa câu không phát lại chunk cũ; transcript khớp phần xác nhận playback, unknown không là câu đã hỏi/evidence; mất mạng/token hết hạn không nhân turn/session; hết recovery budget kết thúc có lý do.

- [ ] **S4-04 — Cổng browser audio và số đo**
- **Vai trò chính:** AI Engineer; phối hợp BA, recruiter/người duyệt tiếng Việt, Fullstack Developer, DevOps.
- **Tiền đề:** S4-03, S0-04.
- **Phạm vi:**
  - Chạy browser/mạng mục tiêu với giọng Bắc/Trung/Nam, Việt–Anh, nhiễu, echo, ngập ngừng; đối chiếu lỗi entity/phủ định riêng theo nhóm.
  - Chạy consent, interruption, correction, reconnect, end và case policy qua voice; nghe đối chiếu transcript bằng synthetic hoặc listening sample có consent riêng.
  - Đo p50/p95 end-of-speech thực → first audible playback, endpointing và từng chặng; ghi cỡ mẫu, browser/mạng/region/concurrency/context.
  - Tổng hợp lỗi, tỷ lệ cắt sai/ngắt thành công và chi phí LiveKit/STT/LLM/TTS/hạ tầng gồm retry; so với ngưỡng đã duyệt, không coi mục tiêu kiến trúc là SLA.
- **Đầu ra:** biên bản cổng audio, cấu hình và bảng số đo có giới hạn.
- **Nghiệm thu:** đạt tiêu chí bộ case/ngưỡng đã thống nhất; không output stale, không mất/trùng phiên; transcript/report không dùng lời chưa phát; recruiter/người duyệt tiếng Việt ký duyệt hoặc ghi blocker chặn demo.

**Exit gate:** đạt cổng browser audio của validation trước demo; ghi rõ số đo thực và phạm vi môi trường, không suy rộng khả năng tiếng Việt từ một mẫu.

## Sprint 5 — Demo nội bộ và vận hành có kiểm soát

**Mục tiêu:** demo synthetic có người duyệt, phục hồi/xóa được và công bố giới hạn.

- [ ] **S5-01 — Deploy và quan sát tối thiểu**
- **Vai trò chính:** DevOps; phối hợp Fullstack Developer, AI Engineer.
- **Tiền đề:** S4-04, S1-04.
- **Phạm vi:**
  - Deploy web/API/worker/postgres, HTTPS/domain, CORS allowlist và đường media; giữ provider secret server-side và auth scoped.
  - Worker dài hạn có restart/graceful shutdown; readiness không nhận việc khi DB/provider cấu hình hỏng, kiểm tra lại migration trước deploy.
  - Theo dõi health, room/worker, lỗi provider/quota, job backlog/retry và cost; log ID giả danh, không token/nội dung cá nhân đầy đủ.
- **Đầu ra:** môi trường demo và dashboard/cảnh báo tối thiểu.
- **Nghiệm thu:** browser mục tiêu dùng mic/playback được qua HTTPS; origin ngoài danh sách và quyền sai bị chặn; restart worker phục hồi job; operator nhận biết backlog/provider lỗi mà không cần đọc transcript.

- [ ] **S5-02 — Backup, retention, xóa và room CV**
- **Vai trò chính:** Fullstack Developer; phối hợp DevOps, BA, chủ sở hữu riêng tư, AI Engineer.
- **Tiền đề:** S5-01, S0-02, S3-01.
- **Phạm vi:**
  - Thực thi retention/xóa riêng transcript/correction/profile/report/events và cache/provider copies theo chính sách; backup có thời hạn/giới hạn công bố.
  - Backup PostgreSQL và thực hành restore; áp lại tombstone/yêu cầu xóa, kiểm tra job trước publish để không hồi sinh dữ liệu.
  - Retention/xóa room CV từ trước session, quarantine/rejected/orphan files, private objects/checksums/metadata và copies/backups; fresh auth signed URL TTL ngắn assigned HR/worker khi cần, không candidate default download.
  - Scan/report/retry jobs và restore phải kiểm tra tombstone trước publish; file integrity checksum/version immutable, không bịa URI khi failure. Recording/export future OUT OF SCOPE, không triển khai capture hoặc controls; CV storage vẫn bắt buộc.
- **Đầu ra:** quy trình và bằng chứng restore/xóa room/CV/transcript/report.
- **Nghiệm thu:** dữ liệu hết hạn/xóa không xem lại theo policy; job/restore không hồi sinh tombstone; không giữ report vô hạn, URL trái quyền bị từ chối, CV copies/backups có giới hạn công bố, không recording/export capture.

- [ ] **S5-03 — UAT demo và ký duyệt theo vai trò**
- **Vai trò chính:** BA; phối hợp recruiter, operator, Fullstack Developer, AI Engineer, chủ sở hữu riêng tư.
- **Tiền đề:** S5-02, S3-04, S4-04.
- **Phạm vi:**
  - Chạy E2E synthetic từ tạo/duyệt campaign, invitation/consent đến voice, report/evidence và human review trên môi trường demo.
  - Chạy negative access, token refresh, mic/network/provider lỗi, restart/retry, stale session và retention/restore; đối chiếu cả ba cổng validation.
  - Recruiter đánh giá usefulness/công bằng/thiếu dữ liệu; ghi lỗi còn mở, mức chấp nhận và cá nhân chịu trách nhiệm trước khi dùng dữ liệu thật.
- **Đầu ra:** hồ sơ UAT có input/config/test version, kết quả, evidence và chữ ký theo vai trò.
- **Nghiệm thu:** mọi case bắt buộc có kết quả pass và người duyệt; không dùng quyền operator để bypass nội dung; không tự tuyển/loại; lỗi không chấp nhận được chặn demo, không ghi hoàn tất giả.

- [ ] **S5-04 — Runbook và bàn giao giới hạn demo**
- **Vai trò chính:** DevOps; phối hợp BA, Fullstack Developer, AI Engineer, recruiter.
- **Tiền đề:** S5-03.
- **Phạm vi:**
  - Ghi startup/deploy/rebuild/shutdown, migration, secret rotation, retry job, xử lý provider/mic/network lỗi, restore và yêu cầu xóa; không dùng down xóa volume thường lệ.
  - Bàn giao cấu hình provider/SDK/region, số đo latency/chất lượng, chi phí thực gồm retry và điều kiện đo; phân biệt số đo với dự báo.
  - Ghi quyết định chưa mở rộng, lỗi còn chấp nhận, owner và điều kiện kiểm tra lại trước pilot; không tuyên bố production-ready.
- **Đầu ra:** runbook, biên bản bàn giao và danh sách giới hạn/chi phí.
- **Nghiệm thu:** operator thực hiện được một bài phục hồi theo runbook; recruiter xác nhận evidence/report hữu ích trong phạm vi demo; BA kiểm tra không có lịch/giá/SLA hoặc kết quả triển khai không có bằng chứng.

**Exit gate:** đạt cổng demo nội bộ của validation, có chữ ký recruiter/operator/chủ sở hữu riêng tư và bằng chứng recovery/security/xóa. Đây không phải quyền tự động mở pilot hoặc dùng dữ liệu thật.

## Đối chiếu phạm vi trước khi đóng kế hoạch

| Nhóm checklist | Task chịu trách nhiệm chính |
| --- | --- |
| BA: phạm vi, mẫu, rubric/FAQ, pha, quyền, consent, guardrail, report, case | S0-01, S0-02, S0-04, S2-04, S5-03 |
| DevOps: versions/env, DB/volume, Cloud, container/compose/readiness/CI/local | S1-01, S1-02, S1-03, S1-04 |
| DevOps: HTTPS/CORS, worker, monitoring, backup/restore; private CV storage/scanner bắt buộc | S1-04, S5-01, S5-02, S5-04 |
| Fullstack: hợp đồng/migration, campaign/auth/consent, tokens/client, persistence | S0-03, S1-02, S2-01, S2-02, S2-03, S4-01, S4-03 |
| Fullstack: durable jobs/review, quyền âm tính, lỗi và retention | S3-01, S3-03, S5-02, S5-03 |
| AI: provider/plugins, controller/FAQ/semantic guardrails, correction/evidence | S1-03, S2-03, S2-04, S3-02 |
| AI: report recovery, interruption/delivery, giọng/nhiễu/timeout/latency/cost | S3-04, S4-02, S4-03, S4-04 |
| Tích hợp: text → browser audio → demo synthetic có người duyệt | S3-04, S4-04, S5-03, S5-04 |

Ma trận policy đầy đủ giữ ở validation-plan, không sao chép thành danh sách ticket nhỏ. Kế hoạch này chưa chứng minh app, provider, số đo hay cổng nghiệm thu nào đã đạt.
