# VEO ABSTRACT BACKGROUND PROMPT FACTORY

## Loop Video Suite (ban day du)

Chạy `run_loop_video_suite.bat` hoặc `python loop_video_suite.py` để mở màn hình
chính. Bản Suite mới dùng một cửa sổ duy nhất với hai tab `Loop Video` và
`Audio + Video + Intro`. Toàn bộ chức năng cũ được giữ nguyên, tab mới không mở
thêm cửa sổ hay tiến trình GUI riêng.

Giao diện Mint Workspace có Light/Dark Mode và tự nhớ lựa chọn gần nhất tại
`%APPDATA%\LoopVideoSuite\settings.json`. Chỉ một tab được phép mã hóa tại một
thời điểm để tránh hai tác vụ tranh GPU, ổ đĩa và thư mục tạm.

Giao diện sử dụng `ttkbootstrap` với hai theme tùy chỉnh `mint-light` và
`mint-dark`, gồm toggle NVENC, nút outline, tiến trình striped và trạng thái
focus/disabled nhất quán.

## Mini Tool Loop Video

Chạy `run_video_loop.bat` hoặc `python video_loop_tool.py`. Tool cần `ffmpeg` và
`ffprobe` có trong PATH, hỗ trợ chọn số lượng video không giới hạn và hai chế độ:

- `1-1`: mỗi video gốc tạo thành một video dài theo số giờ/phút đã nhập.
- `1-nhiều`: hòa trộn tất cả video đã chọn thành một chu kỳ rồi xuất một video dài.

Tool tạo một chu kỳ có crossfade ở điểm nối, sau đó lặp chu kỳ bằng stream copy để
xử lý video dài hiệu quả. Tùy chọn NVIDIA NVENC dùng GPU để mã hóa chu kỳ; có thể
bỏ chọn để dùng libx264 trên CPU. Video đầu ra là MP4 H.264, 30 FPS và không giữ âm thanh.
Bitrate mặc định 10 Mbps cho dung lượng khoảng 4,5 GB mỗi giờ; có thể chỉnh trực tiếp
trên giao diện. Dung lượng thực tế có thể chênh lệch nhẹ do cấu trúc video và container.

## Audio + Video minh họa

Chạy `run_audio_full.bat` hoặc `python audio_full_tool.py`. Chức năng batch riêng này:

- Đọc chính xác thời lượng từng audio lời thoại.
- Đặt intro kênh ở đầu, sau đó loop video minh họa đến hết thời lượng audio.
- Ghép lời thoại vào video và xuất tên có hậu tố `_FULL.mp4`.
- Tái sử dụng một chu kỳ video minh họa cho toàn bộ batch để xử lý số lượng lớn.

Để tự nhận intro theo kênh, đặt audio trong thư mục kênh, ví dụ
`Audio/Kenh_A/tap_01.mp3`, và đặt `Kenh_A.mp4` trong thư mục intro. Nếu không tìm
thấy intro theo tên thư mục cha hoặc tiền tố tên audio, tool dùng intro mặc định.

### Batch audio số lượng lớn

Trong tab `Audio + Video + Intro`, bấm `Nạp thư mục + thư mục con` và chọn thư
mục gốc chứa toàn bộ audio. Tool quét đệ quy, loại file trùng và hiển thị trước
thời lượng cùng intro đã khớp cho từng audio.

Khi chạy, giao diện hiển thị `Tổng`, `Hoàn tất`, `Thất bại`, `Đang chờ`, phần
trăm file hiện tại và phần trăm toàn batch. Khu vực `Tiến trình` chứa log dễ đọc;
`FFmpeg Log` chứa log kỹ thuật trực tiếp và có thể lưu thành file UTF-8. Một
audio lỗi được đánh dấu riêng, sau đó batch tiếp tục với audio kế tiếp.

Không có giới hạn số file từ ứng dụng. Để ổn định GPU và ổ đĩa, tool xử lý tuần
tự một đầu ra tại một thời điểm. Nên bảo đảm thư mục tạm và thư mục xuất còn đủ
dung lượng trước khi chạy batch nhiều giờ.

### Audio intro theo kênh

Khi nạp một thư mục gốc, tool tự quét cả audio và video minh họa trong mọi thư
mục con. File audio có tên `<Kênh>-Intro`, ví dụ `K2-Intro.wav`, không được xem
là một lời thoại riêng. Tool tự nối intro đó vào đầu mọi audio thuộc kênh `K2`,
sau đó loop video cùng tên với lời thoại đến đúng tổng thời lượng intro + lời
thoại. Ví dụ `K2-Intro.wav + K2-V10.wav + K2-V10.mp4` tạo ra
`K2-V10_FULL.mp4`.

Ứng dụng có hai giao diện: desktop Tkinter cho Windows và Streamlit. Cả hai tạo theo batch từ 1 đến 1.000 prompt tiếng Anh cho video background trừu tượng Google Veo qua API tương thích OpenAI của 9Router.

## Yêu cầu hệ thống

- Windows 10/11.
- Python 3.11 trở lên.
- 9Router đang chạy và một model chat có thể trả JSON.
- Vision model tương thích OpenAI multimodal nếu dùng phân tích ảnh.

## Cài đặt trên Windows

Mở PowerShell hoặc Command Prompt tại thư mục dự án:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Sửa `.env`, hoặc tạo `.streamlit/secrets.toml` từ file mẫu. Không commit hai file chứa key này.

```env
NINE_ROUTER_BASE_URL=http://localhost:20128/v1
NINE_ROUTER_API_KEY=your_real_key
NINE_ROUTER_MODEL=your_model_id
NINE_ROUTER_VISION_MODEL=optional_vision_model_id
```

Khởi chạy:

```powershell
streamlit run app.py
```

## Chạy ứng dụng desktop Tkinter

Sau khi cài dependencies, chạy một trong hai cách:

```powershell
python desktop_app.py
```

Hoặc nhấp đúp `run_desktop.bat`.

Giao diện desktop tự động lưu Base URL, API key, model và các tham số API tại `%APPDATA%\VeoPromptFactory\settings.json`. API key không được ghi dạng rõ: ứng dụng dùng Windows DPAPI để mã hóa theo tài khoản Windows hiện tại. Key được tự lưu khi test kết nối, tải model, bắt đầu generation, bấm **Lưu API ngay** hoặc đóng ứng dụng. Dùng **Xóa API đã lưu** để xóa cấu hình này.

## Thiết lập 9Router

Trong sidebar, nhập Base URL, API key và model. Thứ tự ưu tiên API key là giao diện, Streamlit Secrets, rồi biến môi trường. Base URL mặc định là `http://localhost:20128/v1`; cảnh báo `/v1` chỉ mang tính hướng dẫn và không tự sửa URL người dùng.

Nhấn **Load Models** để đọc `GET /models`. Nếu endpoint không hoạt động, nhập model ID thủ công. Nhấn **Test Connection** để kiểm tra endpoint model và gửi một chat request JSON ngắn. Kết quả lỗi luôn được làm sạch API key.

## Tạo prompt

1. Chọn số lượng, batch size, tỷ lệ, độ phân giải, thời lượng, FPS, chuyển động, vùng trống, camera, seed và ngưỡng tương đồng.
2. Có thể tải tối đa 10 ảnh và bật vision analysis. Nếu vision không tương thích, ứng dụng cảnh báo và tiếp tục với hướng mặc định hoặc **Custom visual direction**.
3. Nên thử 100 prompt trước. Nhấn **Generate Prompts**, sau đó dùng **Refresh Status** để cập nhật tiến độ.
4. Để tạo 1.000 prompt, giữ batch size 20 và concurrency 2. Ứng dụng chia thành khoảng 50 batch; không gửi 1.000 item trong một request.

Mỗi item được xác thực bằng Pydantic, độ dài từ, required concepts, forbidden terms theo ranh giới từ, exact SHA-256, canonical metadata key, Jaccard, TF-IDF cosine và độ khác biệt metadata. Batch thiếu item sẽ chỉ repair số lượng thiếu.

## Dừng, tiếp tục và checkpoint

Generation chạy ở worker thread. **Stop Generation** đặt stop flag: request đang chạy có thể hoàn tất và được lưu, nhưng batch mới không được gửi. Dùng **Refresh Status**, sau đó **Resume Generation** để tiếp tục.

Checkpoint được ghi atomic sau mỗi batch vào `checkpoints/`. Tab **Checkpoints** hỗ trợ tạo project mới, lưu, tải và xóa có xác nhận. API key, Authorization header và Secrets không được ghi vào checkpoint.

## Kết quả và xuất dữ liệu

Tab **Results** hỗ trợ tìm kiếm, xem đầy đủ positive/negative prompt và tải:

- TXT trình bày từng prompt.
- CSV đầy đủ cột.
- JSON gồm project, statistics và items.
- JSONL gồm một object mỗi dòng.

Tên file gồm tên project, số prompt và thời gian. API key không xuất hiện trong file. Tab **API Logs** chỉ chứa log đã làm sạch và cho phép tải safe log.

## Khắc phục lỗi

- **Không kết nối:** xác nhận 9Router đã chạy, URL/port đúng, URL thường kết thúc `/v1`, firewall không chặn localhost.
- **HTTP 401/403:** API key sai, thiếu quyền hoặc router từ chối; ứng dụng không tự retry các lỗi này.
- **HTTP 429:** giảm concurrency hoặc batch size, kiểm tra quota. Ứng dụng retry exponential backoff có jitter.
- **HTTP 500/502/503/504:** kiểm tra router/provider/model; ứng dụng tự retry trong giới hạn đã chọn.
- **JSON không hợp lệ:** ứng dụng bóc JSON khỏi Markdown/văn bản thừa rồi retry và repair. Nếu vẫn lỗi, xem tab Rejected/API Logs.
- **Model không hỗ trợ ảnh:** tắt vision analysis hoặc chọn vision model khác; nhập hướng hình ảnh thủ công.
- **Model không hỗ trợ tham số:** client có fallback có kiểm soát cho `response_format`, `max_tokens`, `max_completion_tokens`, `temperature` và `top_p`; fallback được ghi trong safe log.
- **Ít item hợp lệ:** tăng độ đa dạng model, giảm nhẹ ngưỡng similarity, kiểm tra prompt length và dùng Retry Failed Batches.

## Bảo mật

Không dán key vào mã nguồn, README, checkpoint, log hoặc file xuất. `.env` và `.streamlit/secrets.toml` đã nằm trong `.gitignore`. Giao diện không in client object hay Authorization header. Khi chia sẻ log, chỉ dùng **Download Safe Log**.

## Cấu trúc module

- `api_client.py`: OpenAI client, model listing, connection test, retry và fallback.
- `prompt_builder.py`: system/user/repair prompt và negative prompt.
- `reference_analyzer.py`: vision analysis và fallback.
- `validator.py`: content validation.
- `uniqueness.py`: hash, canonical key, Jaccard và TF-IDF.
- `generator.py`: batch planning, concurrency, repair và state updates.
- `checkpoint.py`: atomic checkpoint.
- `exporters.py`: TXT/CSV/JSON/JSONL/safe log.
- `app.py`: Streamlit UI và session state.
- `desktop_app.py`: giao diện desktop Tkinter.
- `desktop_settings.py`: lưu cấu hình và mã hóa API key bằng Windows DPAPI.
