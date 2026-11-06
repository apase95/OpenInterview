import asyncio
import os
import sys
import time

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def is_placeholder(val: str | None) -> bool:
    if not val:
        return True
    val = val.strip()
    return "xxxx" in val or "your-project" in val or len(val) < 8

async def test_livekit() -> bool:
    print(f"\n{BOLD}▶ 1. LiveKit admin API (list rooms; not WebRTC)...{RESET}")
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if is_placeholder(url) or is_placeholder(api_key) or is_placeholder(api_secret):
        print(f"  {YELLOW}⚠ Bỏ qua:{RESET} Chưa điền LIVEKIT_URL, LIVEKIT_API_KEY hoặc LIVEKIT_API_SECRET hợp lệ trong .env")
        return False

    try:
        from livekit.api import LiveKitAPI, ListRoomsRequest
        api = LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)
        start = time.perf_counter()
        try:
            rooms = await api.room.list_rooms(ListRoomsRequest())
        finally:
            await api.aclose()
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  {GREEN}✔ Thành công:{RESET} LiveKit admin API")
        print(f"    - Thời gian phản hồi: {elapsed:.1f}ms")
        print(f"    - Số phòng active hiện tại: {len(rooms.rooms)}")
        return True
    except Exception as e:
        print(f"  {RED}✖ LiveKit: {type(e).__name__}{RESET}")
        return False

async def test_gemini() -> bool:
    print(f"\n{BOLD}▶ 2. Kiểm tra Google Gemini (LLM Generation)...{RESET}")
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GEMINI_CONTROLLER_MODEL", "gemini-3.5-flash-lite")

    if is_placeholder(api_key):
        print(f"  {YELLOW}⚠ Bỏ qua:{RESET} Chưa điền GOOGLE_API_KEY trong .env")
        return False

    try:
        from livekit.plugins import google
        from livekit.agents import llm as lk_llm
        from livekit.agents import utils

        async with utils.http_context.open():
            llm = google.LLM(model=model, api_key=api_key)
            ctx = lk_llm.ChatContext()
            ctx.add_message(
                role="user",
                content="Bạn là trợ lý phỏng vấn tuyển dụng. Hãy đưa ra 1 câu chào ứng viên ngắn gọn, lịch sự bằng tiếng Việt."
            )
            start = time.perf_counter()
            stream = llm.chat(chat_ctx=ctx)
            first_token_time = None
            full_text = ""
            async for chunk in stream:
                if chunk.delta and chunk.delta.content:
                    if first_token_time is None:
                        first_token_time = (time.perf_counter() - start) * 1000
                    full_text += chunk.delta.content
            total_time = (time.perf_counter() - start) * 1000
            ttft_str = f"{first_token_time:.1f}ms" if first_token_time else "N/A"
            if not full_text.strip():
                print("  Gemini: empty text stream")
                return False
            print(f"  {GREEN}✔ Thành công:{RESET} Gemini nonempty text stream")
            print(f"    - Thời gian đến token đầu (TTFT): {ttft_str} (Tổng: {total_time:.1f}ms)")
            return True
    except Exception as e:
        print(f"  {RED}✖ Gemini: {type(e).__name__}{RESET}")
        return False

async def test_deepgram() -> bool:
    print(f"\n{BOLD}▶ 3. Deepgram authentication (not transcription)...{RESET}")
    api_key = os.getenv("DEEPGRAM_API_KEY")

    if is_placeholder(api_key):
        print(f"  {YELLOW}⚠ Bỏ qua:{RESET} Chưa điền DEEPGRAM_API_KEY trong .env")
        return False

    try:
        import aiohttp
        headers = {"Authorization": f"Token {api_key}"}
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.deepgram.com/v1/projects", headers=headers) as resp:
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status == 200:
                    print(f"  {GREEN}✔ Thành công:{RESET} Deepgram authentication ({elapsed:.1f}ms)")
                    return True
                else:
                    print(f"  {RED}✖ Deepgram: HTTP {resp.status}{RESET}")
                    return False
    except Exception as e:
        print(f"  {RED}✖ Deepgram: {type(e).__name__}{RESET}")
        return False

async def test_elevenlabs() -> bool:
    print(f"\n{BOLD}▶ 4. Kiểm tra ElevenLabs Flash v2.5 (TTS Vietnamese)...{RESET}")
    api_key = os.getenv("ELEVEN_API_KEY")
    model = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")

    if is_placeholder(api_key):
        print(f"  {YELLOW}⚠ Bỏ qua:{RESET} Chưa điền ELEVEN_API_KEY trong .env")
        return False

    try:
        from livekit.plugins import elevenlabs
        from livekit.agents import utils

        async with utils.http_context.open():
            tts = elevenlabs.TTS(model=model, api_key=api_key)
            test_text = "Xin chào bạn, chúc bạn một buổi phỏng vấn đạt kết quả tốt."
            start = time.perf_counter()
            stream = tts.synthesize(test_text)
            first_chunk_time = None
            total_frames = 0
            async for chunk in stream:
                if first_chunk_time is None:
                    first_chunk_time = (time.perf_counter() - start) * 1000
                total_frames += 1
            total_time = (time.perf_counter() - start) * 1000
            latency_str = f"{first_chunk_time:.1f}ms" if first_chunk_time else f"{total_time:.1f}ms"
            if total_frames == 0:
                print("  ElevenLabs: empty audio stream")
                return False
            print(f"  {GREEN}✔ Thành công:{RESET} ElevenLabs audio frames received (not listened to)")
            print(f"    - Độ trễ chunk âm thanh đầu: {latency_str} (Tổng: {total_time:.1f}ms, Frames: {total_frames})")
            return True
    except Exception as e:
        print(f"  {RED}✖ ElevenLabs: {type(e).__name__}{RESET}")
        return False

async def main():
    from dotenv import load_dotenv
    load_dotenv()
    print(f"{BOLD}======================================================{RESET}")
    print(f"{CYAN}{BOLD}  OPENINTERVIEW — SPRINT 1 SMOKE TEST SUITE  {RESET}")
    print(f"{BOLD}======================================================{RESET}")
    print("Đang nạp cấu hình từ .env...")

    results = {}
    for name, check in (
        ("LiveKit admin API", test_livekit),
        ("Google Gemini (LLM)", test_gemini),
        ("Deepgram authentication", test_deepgram),
        ("ElevenLabs (TTS)", test_elevenlabs),
    ):
        try:
            results[name] = await asyncio.wait_for(check(), timeout=30)
        except Exception as e:
            print(f"  {name}: {type(e).__name__}")
            results[name] = False

    print(f"\n{BOLD}==================== TỔNG KẾT SMOKE TEST ===================={RESET}")
    all_passed = True
    for name, ok in results.items():
        status = f"{GREEN}PASS (HỢP LỆ){RESET}" if ok else f"{RED}FAIL / CHƯA ĐIỀN KEY{RESET}"
        if not ok:
            all_passed = False
        print(f"  • {name:<25}: {status}")
    print(f"{BOLD}============================================================={RESET}")

    if all_passed:
        print(f"\n{GREEN}{BOLD}🎉 TẤT CẢ 4/4 PROVIDER ĐÃ XÁC THỰC THÀNH CÔNG!{RESET}")
        print("Provider smoke passed only.")
    else:
        print(f"\n{YELLOW}Lưu ý: Vui lòng kiểm tra lại các Secret Key bị lỗi trong .env và chạy lại script.{RESET}\n")
    print("Not validated: full pipeline, browser/WebRTC, STT, report, or Sprint 1 exit gate")
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
