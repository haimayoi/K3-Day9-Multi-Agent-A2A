# Team Task Split — 3 Người / 3 Giờ (Checkpoint 2)

> Tài liệu điều phối nội bộ nhóm, không phải deliverable chấm điểm. Mục tiêu: hoàn thành pipeline multi-agent xử lý 50 case trong `input/`, sinh đúng 50 file `output/EC_001.json … EC_050.json` đúng schema, kèm `architecture.md`, `metadata.json`, `trace.jsonl` và 3 báo cáo cá nhân.

## 0. Trước khi bắt đầu (0:00 – 0:15, cả 3 người)

**Đã chốt (2026-08-05):**

- **Model:** `gpt-4o-mini` (OpenAI), dùng cho mọi agent cần gọi LLM. ⚠️ OpenAI không công bố chính thức parameter count của gpt-4o-mini — số `~8B` trong `logging/metadata.json` chỉ là ước tính cộng đồng, không phải số chính thức. Team đã chấp nhận rủi ro này; nếu giám khảo bắt lỗi vượt hạn mức 10B, đây là điểm cần giải trình.
- **Interface + helper dùng chung đã viết sẵn** trong `src/shared/` — không ai tự viết lại các phần này, chỉ import:
  - `src/shared/config.py` — tên model, danh sách `PRIMARY_ISSUES`/`ROOT_CAUSE_CODES`/`RESOLUTION_ACTIONS`/giới hạn số lượng ID.
  - `src/shared/data_loader.py` — `get_data_store()`: load + cache 9 CSV một lần duy nhất, có sẵn `order_exists`, `get_items`, `get_payments`, `seller_exists`.
  - `src/shared/money.py` — `round_brl()`, `sum_brl()`, `within_tolerance()` (dùng Decimal, tránh sai số float).
  - `src/shared/evidence.py` — `order_evidence()`, `item_evidence()`, `payment_evidence()`, `seller_evidence()`, `policy_evidence()`, và `validate_evidence_ids()` (Verifier dùng để bắt false positive).
  - `src/shared/interfaces.py` — `FulfillmentResult`, `PaymentResult`, `CaseOutput` (TypedDict) + 2 stub `analyze_fulfillment()` / `analyze_payment()` định nghĩa contract giữa A/B/C.
  - `src/shared/llm_client.py` — `call_llm(system_prompt, user_prompt)` gọi `gpt-4o-mini`, đọc `OPENAI_API_KEY` từ `.env` (copy từ `.env.example`).
- **File stub đã tạo sẵn cho từng người** (chỉ còn điền logic, không đổi tên hàm/tham số):
  - Person A → `src/agents/fulfillment_agent.py`
  - Person B → `src/agents/payment_agent.py`
  - Person C → `src/agents/coordinator.py`, `src/agents/verifier.py`, `main.py` (harness đọc `input/`, ghi `output/` + `logging/trace.jsonl`)
- **Còn phải chốt trong 15 phút đầu:**
  1. **Framework orchestration** — hiện để `TODO_FRAMEWORK` trong `src/shared/config.py` và `logging/metadata.json`. Chọn xong thì sửa 2 chỗ này (vd. `"custom-python"` nếu chỉ dùng function-calling thuần, hoặc tên framework nếu dùng LangGraph/CrewAI).
  2. **Ai giữ nhánh chính / merge code** — tránh conflict khi cả 3 push cùng lúc. Khuyến nghị: mỗi người làm trên branch riêng, merge vào `main` ở mốc 1:15 và 2:15.
  3. Mỗi người `pip install -r requirements.txt`, copy `.env.example` → `.env`, điền `OPENAI_API_KEY` thật (không commit `.env` — đã có trong `.gitignore`).

---

## 1. Person A — Fulfillment Agent (Order & Seller + Delivery)

### Phạm vi
Trả lời: đơn có bị hủy/unavailable không? seller có bàn giao trễ hạn (`shipping_limit_date`) không? carrier có giao trễ so với `estimated_date` không?

### Rule cần cài đặt (theo thứ tự ưu tiên trong README §4)
| Primary issue | Điều kiện | Root cause code |
|---|---|---|
| `canceled_order_paid` | `order_status = canceled` và tổng payment > 0 | `ORDER_CANCELED_AFTER_PAYMENT` |
| `unavailable_order_paid` | `order_status = unavailable` và tổng payment > 0 | `ORDER_UNAVAILABLE_AFTER_PAYMENT` |
| `late_delivery_seller` | Giao sau `estimated_date` **và** carrier nhận hàng sau `shipping_limit_date` của item thuộc seller đó | `SELLER_HANDOFF_AFTER_LIMIT` |
| `late_delivery_logistics` | Giao sau `estimated_date` **và** carrier nhận hàng không muộn hơn `shipping_limit_date` | `CARRIER_DELIVERED_AFTER_ESTIMATE` |
| (một phần của) `unsupported_late_claim` | Giao không muộn hơn `estimated_date` | `DELIVERY_WITHIN_ESTIMATE` |

Lưu ý: nếu order có nhiều item/seller, seller coi là trễ nếu **bất kỳ item nào của seller đó** có `order_delivered_carrier_date > shipping_limit_date`. Bộ 50 case chính thức không có tình huống mơ hồ giữa nhiều seller — không cần xử lý edge case đó.

### Dữ liệu cần join
- `orders.csv` (order_status, order_estimated_delivery_date, order_delivered_carrier_date, order_delivered_customer_date)
- `order_items.csv` (order_item_id, seller_id, shipping_limit_date, price)
- `sellers.csv` (seller_id — để xác nhận tồn tại)

### Việc cần làm
1. Viết `analyze_fulfillment(order_id)`.
2. Xử lý case order không có item row → `item_ids`, `seller_ids` trả về rỗng.
3. Test tay với ít nhất 5 case trong `input/` (chọn case có vẻ liên quan giao hàng/hủy đơn — đọc `customer_request.message`).
4. Bàn giao interface cho Person C ở mốc 1:15.
5. Viết phần "Order & Seller Agent" + "Delivery Agent" trong `architecture.md` (vai trò, input/output, quyền truy cập file nào).

---

## 2. Person B — Payment Agent

### Phạm vi
Đối soát payment với item + freight. Xác định có phải `valid_split_payment` không.

### Rule cần cài đặt
| Primary issue | Điều kiện | Root cause code |
|---|---|---|
| `valid_split_payment` | Có từ 2 payment row trở lên; tổng payment khớp tổng item + freight trong sai số 0.10 BRL | `MULTIPLE_PAYMENTS_RECONCILED` |

Payment agent cũng là nguồn tính `item_total_brl`, `freight_total_brl`, `payment_total_brl` dùng chung cho **mọi** primary_issue khác (không chỉ split payment) — đây là phần Person C sẽ gọi lại nhiều lần nên cần chuẩn ngay từ đầu.

### Dữ liệu cần join
- `order_payments.csv` (payment_sequential, payment_value) — group theo `order_id`
- `order_items.csv` (price, freight_value) — tổng theo `order_id`

Lưu ý quan trọng từ README: `payment_value` là số tiền của **từng dòng payment**, không phải giá trị mỗi installment — không chia lại theo `payment_installments`.

### Việc cần làm
1. Viết `analyze_payment(order_id)`.
2. Xử lý order không có item row → `item_total_brl = 0.0`, `freight_total_brl = 0.0`.
3. Test tay với case có nhiều payment row (tìm trong `order_payments.csv` những `order_id` có ≥2 dòng).
4. Bàn giao interface cho Person C ở mốc 1:15.
5. Viết phần "Payment Agent" trong `architecture.md`.

---

## 3. Person C — Coordinator + Policy Agent + Verifier Agent + I/O Harness

### Phạm vi
Đây là phần nặng nhất về tích hợp — nên bắt đầu ngay từ 0:15 với phần I/O trước (không phụ thuộc A/B), rồi mới lắp ráp Policy khi A/B bàn giao ở mốc 1:15.

### 3.1 I/O Harness (làm trước, 0:15–1:15)
- Đọc từng file `input/EC_*.json`.
- Gọi (sau này) `analyze_fulfillment` + `analyze_payment`.
- Ghi `output/EC_*.json` đúng tên file khớp input.
- Ghi `logging/trace.jsonl`: 1 dòng JSON/case, log lại các bước handoff giữa agent (không append từ lần chạy cũ — chỉ giữ lượt chạy mới nhất).
- Ghi `logging/metadata.json`: model dùng cho từng agent, parameter size, framework, runtime.

### 3.2 Policy Agent — bảng ưu tiên (ráp lại sau khi có A/B)
Áp dụng đúng **thứ tự ưu tiên từ trên xuống** trong README §4 (đừng tự đổi thứ tự):
1. `canceled_order_paid` / `unavailable_order_paid` (từ A)
2. `late_delivery_seller` / `late_delivery_logistics` (từ A)
3. `valid_split_payment` (từ B)
4. `unsupported_late_claim` (giao đúng hạn + payment khớp → `reject_late_refund`)

Tính `recommended_refund_brl`:
- `canceled_order_paid` / `unavailable_order_paid` → tổng payment
- `late_delivery_seller` / `late_delivery_logistics` → tổng freight
- còn lại → `0`

`case_status`: `action_required` nếu có refund > 0, ngược lại `no_action`.

`resolution_actions`: map 1-1 theo bảng README (`issue_full_refund`, `refund_freight`, `explain_valid_split_payment`, `reject_late_refund`).

### 3.3 Verifier Agent (chạy cuối, trước khi ghi file)
Checklist bắt buộc — **case fail cái nào cũng có thể bị hard gate = 0 điểm**, nên đừng bỏ qua:
- [ ] Mọi evidence ID đúng format (`order:`, `item:`, `payment:`, `seller:`, `policy:`) và **thực sự tồn tại** trong CSV (không tự bịa order/item/seller không có thật).
- [ ] `primary_issue` là 1 trong 6 giá trị hợp lệ.
- [ ] `confidence` ∈ [0, 1].
- [ ] Giới hạn số lượng: tối đa 5 ID/entity set, 10 evidence, 3 root causes, 3 responsible parties, 5 actions.
- [ ] Tiền làm tròn đúng 2 chữ số thập phân.
- [ ] Order không có item → `item_ids`/`seller_ids` rỗng, `item_total_brl`/`freight_total_brl` = `0.0`.
- [ ] File output tồn tại đủ 50 file, tên khớp input.

### Việc cần làm
1. Dựng harness đọc/ghi file trước (0:15–1:15), dùng dữ liệu giả lập (mock A/B) để test luồng.
2. Nhận interface thật từ A/B ở mốc 1:15, thay mock bằng real call.
3. Viết Verifier, chạy qua toàn bộ 50 case ở 2:15–2:45.
4. Viết `architecture.md` phần Coordinator, Verifier, sơ đồ tổng + luồng handoff (tổng hợp lại phần A/B viết).
5. Cuối buổi: nén `output/` thành zip (chỉ chứa đúng 50 file JSON, không kèm code/`.env`), đảm bảo source code đã commit đầy đủ trước khi nộp zip.

---

## 4. Timeline tổng hợp

| Giờ | Person A | Person B | Person C |
|---|---|---|---|
| 0:00–0:15 | Sync chung: chọn model/framework, thống nhất interface & helper dùng chung | (như A) | (như A) |
| 0:15–1:15 | Build `analyze_fulfillment`, test tay 5 case | Build `analyze_payment`, test tay case multi-payment | Build I/O harness (đọc input, ghi output/trace) với mock data |
| 1:15–1:30 | **Bàn giao interface thật cho C** | **Bàn giao interface thật cho C** | Lắp real A/B vào harness, fix mismatch |
| 1:30–2:15 | Chạy full 50 case, debug case sai ở domain mình (giao hàng/hủy đơn) | Chạy full 50 case, debug case sai ở domain mình (payment) | Ráp Policy Agent (bảng ưu tiên), chạy full 50 case |
| 2:15–2:45 | Support debug nếu C phát hiện case sai do fulfillment | Support debug nếu C phát hiện case sai do payment | Chạy Verifier checklist, fix case fail hard gate |
| 2:45–3:00 | Viết phần mình trong `architecture.md`, bắt đầu báo cáo cá nhân | Viết phần mình trong `architecture.md`, bắt đầu báo cáo cá nhân | Zip `output/`, commit toàn bộ code, hoàn thiện `metadata.json`/`trace.jsonl`, chốt `architecture.md` |

---

## 5. Checklist nộp bài (làm cùng lúc 2:45–3:00)

- [ ] `output/` có đúng 50 file `EC_001.json` → `EC_050.json`, không file thừa.
- [ ] Toàn bộ source code đã commit lên repo **trước khi** tạo file zip để nộp.
- [ ] `.env` chứa API key **không được commit** (kiểm tra `.gitignore`).
- [ ] Tên model khai báo rõ trong code (không chỉ trong `.env`).
- [ ] `architecture.md` có sơ đồ agent, vai trò, quyền truy cập, luồng handoff.
- [ ] `metadata.json` điền đủ: model, parameter size, framework, runtime.
- [ ] `trace.jsonl` là lượt chạy thật gần nhất của đủ 50 case (không phải log cũ/append chồng).
- [ ] Mỗi người tự viết `individual_5SoCuoiMHV_HoVaTen.md` của mình (đổi tên file theo đúng format, không copy của nhau).
- [ ] Zip nộp **chỉ chứa** folder `output/` — không kèm source code, `.env`, file audit.
