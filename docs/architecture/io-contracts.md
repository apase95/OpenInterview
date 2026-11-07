# Hợp đồng đầu vào và đầu ra

Technical v1 shapes, routes and implementation states now live in the
[API/data contract](api-data-contract.md). This document remains the logical/media
design; domain `/v1` routes are not implemented. Implemented HTTP routes are
`/health`, `/ready`, and the separate development-only, gated `/local/voice`
session endpoints described in the [development guide](../contributing/development.md).

Đây là hợp đồng logic đề xuất cho MVP, chưa phải API, schema DB hay tính năng đã triển khai. Áp dụng [yêu cầu nghiệp vụ](../business/requirements.md), [điều phối](conversation-workflow.md) và [quy tắc artifact](data-artifacts.md). Không yêu cầu CV từ candidate; HR upload CV tùy chọn lúc tạo room. Không PSTN; quyết định tuyển thuộc con người. Desktop UI đúng [7 trang](../product/README.md), không candidate profile/CV portal. Recording/export future OUT OF SCOPE.

## Ranh giới dữ liệu

| Dữ liệu | Producer → consumer | Định dạng và mức cần thiết | Kiểm tra | Vòng đời |
| --- | --- | --- | --- | --- |
| Giọng candidate | Mic browser → LiveKit → Python agent/STT | Media WebRTC; bắt buộc cho voice session | Consent trước thu nội dung, quyền mic, track đúng identity/room, codec và mức âm phù hợp | Buffer tạm; streaming không có nghĩa đã lưu audio |
| Ngôn ngữ | Backend → controller/STT/TTS | Speech `vi`, website English, không language switch | Provider đã kiểm chứng; không suy ra quốc tịch | Cấu hình phiên được lưu |
| Consent | Candidate → backend/controller | Lựa chọn transcript/phiên/report, notice version và UTC | Trước mic/media tại Join room; quyền mic không là informed consent; recording ngoài active MVP | Lưu bằng chứng lựa chọn tối thiểu |
| Room/CVAttachment | HR → backend/private object store | Exact identity/campaign version + optional attachment ID/version/hash hoặc absence; schema đề xuất ở requirements | HR authority/lawful basis/notice trước upload; server kiểm tra relationship, bounded PDF 5 MB configurable proposal, quarantine/scan trước publish; không scan không publish room có file | Draft sửa được; publish/invite khóa; sai CV sau đó revoke/cancel và NEW room, không swap ongoing history; “No CV attached” hợp lệ |
| Metadata phiên | Backend → browser/worker | Opaque tenant/session/campaign IDs, identity scoped, UTC, version; bắt buộc | Auth và quyền tenant/campaign/session; token TTL ngắn, không log token | State/version lưu DB; credential tạm |
| JD và yêu cầu tuyển | Recruiter → backend/bộ sinh câu hỏi | Text có giới hạn kích thước; bắt buộc | Quyền sửa, không rỗng, coi nội dung là dữ liệu không tin cậy | Snapshot có version |
| Câu hỏi lõi/rubric | Recruiter phê duyệt → controller/report | Structured question/criterion IDs, giới hạn followup; bắt buộc | Chặn phiên chưa duyệt; khóa version, không đổi hồi tố | DB nguồn chuẩn |
| FAQ nội bộ | Recruiter → controller/LLM | Context nhỏ có source ID/version, hiệu lực, approval; tùy chọn | Giới hạn kích thước, quyền truy cập, chỉ nguồn duyệt còn hiệu lực; thiếu thì unknown | Snapshot/version được lưu; prompt tạm |
| Thông tin và FAQ candidate | Candidate finalized turns → facts/FAQ/report | Text + collection status + turn refs; trường theo chiến dịch | Không tự điền; tuổi chỉ khi có lý do/consent/pháp lý; không DOB/địa chỉ đầy đủ | Lưu tối thiểu theo consent |
| Lệnh skip/clarify/end/interrupt | Candidate/UI hoặc voice → controller | Control event hoặc ý định đã xác nhận | Thuộc phiên, action allowlist, hạn mức; end không bị bỏ qua vì hết quota | State và sự kiện tối thiểu |

Nội dung candidate/JD không được thay policy, rubric hoặc mở quyền công cụ. Cấu hình provider/region, giới hạn payload và thời hạn token phải chốt trước triển khai; không đưa credential vào hợp đồng xuất.

## Sản phẩm trung gian và đầu ra

| Sản phẩm | Producer → consumer | Hình dạng / bắt buộc | Kiểm tra và lưu trữ |
| --- | --- | --- | --- |
| STT partial | STT → controller | Hypothesis có revision; nội bộ | Tạm thời, không evidence/raw transcript/captions UI |
| STT final | STT → controller/DB | Finalized text + turn ID + audio offsets; cần cho turn candidate | Validate phiên/sequence; giữ nguyên bản final, correction tách riêng; không khẳng định đúng nguyên văn tuyệt đối |
| LLM decision | LLM → controller | Action/criterion/evidence/question có cấu trúc | Controller validate schema, refs, deadline và hạn mức như tài liệu điều phối; không lưu chain-of-thought |
| Text TTS | Controller → TTS | Text đã được policy cho phép + generation ID | Planned text là diagnostic riêng, không phải assistant evidence; hủy generation cũ khi ngắt |
| Audio chunks | TTS → agent → LiveKit → browser | Chunk có generation/sequence, format provider | Buffer hữu hạn; queued khác delivered; chunk bị hủy không được phát lại |
| Audio trả candidate | LiveKit → browser | Voice response; đầu ra chính | Theo dõi playback best-effort; không chứng minh con người thực sự nghe; delivery unknown không tính đã hỏi |
| Status | Controller → browser | Essential short English status/error trong robot stage | Interview chỉ stage + đúng ba controls mic/speaker/End, không captions/timer/extra controls/text fallback |
| Report/evidence | DB + report worker → recruiter | Summary, criterion status, finalized turn refs, reviewer | Theo [báo cáo](../report/interview-report.md); không tự tuyển/loại; persist trước khi báo ready |
| Export/recording (future OUT OF SCOPE) | Artifact job → người có quyền | Thiết kế tương lai, không active MVP/UI | Theo [artifact](data-artifacts.md), cần phê duyệt riêng |

Browser thường thương lượng Opus trên WebRTC. Agent decode/resample sang PCM theo yêu cầu provider thực tế, không áp một chuẩn 16 kHz cho mọi chặng. TTS chuyển format phù hợp track. Future OUT OF SCOPE recording có thể dùng WAV mono PCM với format/sample rate thật; không triển khai capture/export trong MVP.

```mermaid
flowchart LR
    C[Browser mic sau consent] --> L[LiveKit WebRTC]
    L --> A[Agent decode và resample]
    A --> S[STT partial và final]
    S --> V[Controller validate]
    V --> D[(DB finalized turns)]
    V --> M[LLM decision]
    M --> P[Policy gate]
    P --> T[TTS text và chunks]
    T --> L
    L --> B[Browser playback tracking]
    B --> V
    D --> R[Durable report jobs]
    H[HR room CV sau lawful basis] --> Q[Backend validation quarantine scan]
    Q --> O[Private object store bắt buộc cho CV]
```

## Ví dụ event/turn logic

Mọi ví dụ trong hai tài liệu mới là synthetic, không phải dữ liệu phỏng vấn thật. Envelope đề xuất dưới đây biểu diễn một candidate final; không phải endpoint đã có:

```json
{
  "schema_version": "1.0",
  "event_id": "ev_03",
  "event_type": "candidate_turn_finalized",
  "tenant_id": "tn_demo",
  "session_id": "ss_demo",
  "sequence": 3,
  "occurred_at": "2026-11-06T09:00:05Z",
  "turn": {
    "turn_id": "ct_01",
    "speaker": "candidate",
    "kind": "answer",
    "finalized_text": "Tôi đã trực tiếp xử lý yêu cầu hỗ trợ.",
    "audio_start_ms": 2000,
    "audio_end_ms": 5000,
    "stt_revision": 1,
    "source_version": "transcript-v1"
  },
  "provenance": {
    "campaign_version": "campaign-v2",
    "rubric_version": "rubric-v2",
    "stt_config_version": "stt-config-v1"
  }
}
```

`occurred_at` là UTC để audit; audio offsets là ms từ media timeline bắt đầu phiên, không phải epoch hay vị trí byte WAV. Khi reconnect giữ timeline và ghi gap; mapping recording timeline riêng trong metadata. Không dùng thời điểm nhận event thay timestamp audio. Turn ID ổn định cho cùng final; revision/correction có nguồn gốc rõ, không ghi đè mất lịch sử.

Assistant giữ `planned_text` ở sản phẩm generation riêng. Canonical Turn chỉ có phần `finalized_text` xác nhận đã phát, `delivery_status` và offsets tương ứng. Nếu tracking chỉ chứng minh delivered media mà không map chắc text, giữ unknown và không suy đoán prefix từ tỷ lệ thời lượng. Generated → queued → confirmed delivered/partial/unknown là các trạng thái khác nhau; không đồng nghĩa thực sự đã nghe.

## Thứ tự, lỗi và phục hồi MVP

- Backend/controller cấp sequence logic theo phiên; media chunk sequence riêng theo generation. Dedupe event theo `(session_id, event_id)` và final theo turn/revision bằng unique key DB. Persist turn + state trong transaction trước report job tham chiếu; export chỉ future OUT OF SCOPE, không cần Kafka/Redis.
- Reconnect xác thực lại đúng phiên, đối soát sequence/turn đã commit và pending generation. Không blind replay lời hỏi hoặc tạo turn mới vì retry. Event trễ của generation đã hủy bị loại; event ngoài thứ tự chờ đối soát hữu hạn hoặc đánh dấu gap, không âm thầm đảo lịch sử.
- Echo/noise: dùng khả năng echo cancellation/browser và VAD phù hợp, kiểm chứng thực tế; không nhận audio assistant vọng lại thành câu trả lời candidate. Barge-in hủy LLM/TTS, dừng/xóa queue và ghi phần delivery đã xác nhận; phần còn lại unknown/cancelled.
- Timeout/provider lỗi: retry hữu hạn theo cấu hình, báo trạng thái ngắn nếu media còn hoạt động; hết hạn thì kết thúc gián đoạn có lý do. Không bịa transcript/answer. Mic bị chặn thì hướng dẫn thử lại hoặc dừng, không lách consent.
- Backpressure: queue media hữu hạn, giới hạn generation đang hoạt động; ngừng sản xuất/hủy output stale khi consumer chậm. Không âm thầm bỏ candidate audio: ghi gap/partial và hỏi lại khi có thể. Ngưỡng queue/timeout phải đo trước khi chốt, không là SLA.
- Text fallback chỉ là quyết định tùy chọn sau này; MVP không mặc định có kênh trả lời thay voice. Quy tắc consent và provenance vẫn áp dụng nếu bổ sung.

- End intent dừng local media/cancel output ngay, không confirm/forced wrap; backend persist terminal/job idempotently, return Roles inline “Interview ended”. Offline reconcile không resume audio; deadline/connection/delivery vẫn nội bộ. CV chỉ HR reference, không parse/score/nạp prompt hoặc evidence; claims unverified. Private URL TTL ngắn chỉ assigned HR/worker khi cần sau auth, candidate không download mặc định; immutable checksum/version, retention/xóa copies/backups và tombstones theo artifact contract.
