# Báo cáo cá nhân — K3 Day 09 Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Tạ Minh Đức |
| MSSV | 01497 |
| Khóa/Lớp | K3 |
| Vai trò chính | Person B — Payment Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Payment Agent | `src/agents/payment_agent.py` / `analyze_payment(order_id)` | `order_id`, item và payment từ `DataStore` | `PaymentResult` cho Coordinator | Hoàn thành |
| Đối soát thanh toán | Quy tắc `valid_split_payment` | `payment_value`, `price`, `freight_value` | Các tổng BRL, `is_split_payment`, `reconciled` | Hoàn thành |
| Tài liệu kiến trúc | Mục Payment Agent trong `architecture.md` | Contract và luồng handoff | Vai trò, quyền truy cập và output | Hoàn thành |

Payment Agent cung cấp `item_total_brl`, `freight_total_brl` và `payment_total_brl` cho mọi primary issue, đồng thời xác định split payment hợp lệ để Coordinator áp dụng `EC_POLICY_V1` theo đúng thứ tự ưu tiên.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp contract | Coordinator/Policy Agent | Bàn giao `PaymentResult` đúng TypedDict, không làm Coordinator phụ thuộc vào nội bộ Payment Agent |
| Debug payment ID | Coordinator và Verifier | Phân biệt entity ID `<order_id>:<payment_sequential>` với evidence ID `payment:<order_id>:<payment_sequential>` |
| Kiểm tra end-to-end | Pipeline 50 case | Xác minh các trường hợp một/nhiều payment row và order không có item |

## 3. Kết quả theo vai trò

| Nhiệm vụ | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- |
| Tính tổng item, freight và payment | Tổng tiền làm tròn 2 chữ số bằng helper Decimal dùng chung | Chạy agent trên 50 `input/EC_*.json` |
| Nhận diện split payment | Phát hiện 9/50 case: 8 case có 2 row, 1 case có 3 row | Kiểm tra `payment_row_count` và `is_split_payment` |
| Đối soát sai số 0.10 BRL | 42/50 case reconciled; cả 9 split-payment case đều khớp | So sánh payment với item + freight |
| Xử lý order không có item | 8 case trả item/freight bằng `0.0` | Kiểm tra toàn bộ kết quả Payment Agent |

Artifact tiêu biểu là `EC_030`: order `405be8487a7fde1db0bc31ad6b08050a` có 3 payment row, `item_total_brl = 15.90`, `freight_total_brl = 9.94`, `payment_total_brl = 25.84`, do đó `is_split_payment = true` và `reconciled = true`.

## 4. Giải thích kỹ thuật

### Vấn đề cần giải quyết

Một order có thể có nhiều item và nhiều payment row. Mỗi `payment_value` là giá trị của chính payment row, không phải giá trị của từng installment. Kết quả phải chính xác về tiền để Coordinator dùng cho phân loại, hoàn tiền và evidence.

### Cách triển khai

`analyze_payment(order_id)` lấy dữ liệu từ `get_data_store()` để CSV chỉ được load và cache một lần. Hàm cộng `price`, `freight_value` và từng `payment_value`; không chia payment theo `payment_installments`. Split payment được xác định khi có ít nhất 2 payment row. Payment được coi là reconciled khi chênh lệch với item + freight không vượt quá 0.10 BRL.

Các phép tính dùng `sum_brl()`, `round_brl()` và `within_tolerance()` dựa trên `Decimal`. Agent trả toàn bộ payment ID theo contract; việc giới hạn tối đa 5 entity ID thuộc Coordinator/Verifier.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `order_id: str` |
| Dữ liệu đọc | `order_payments` và `order_items` thông qua `DataStore` |
| Output | `PaymentResult`: payment IDs/count, ba tổng BRL, split và reconciled flags |
| Module phụ thuộc | `data_loader.py`, `money.py`, `config.py`, `interfaces.py` |
| Module dùng output | `coordinator.py`, sau đó `verifier.py` |
| Edge case | Không có item/payment, nhiều payment row, sai số tiền, nhầm payment với installment |

### Cách xác minh

```powershell
py -3 -c "from src.agents.payment_agent import analyze_payment; print(analyze_payment('405be8487a7fde1db0bc31ad6b08050a'))"
```

- **Kết quả mong đợi:** 3 payment row; item 15.90 BRL; freight 9.94 BRL; payment 25.84 BRL; split và reconciled là `True`.
- **Kết quả thực tế:** Đúng như mong đợi. Kiểm tra 50 case cho thấy 9 split payment, 42 reconciled và 8 order không có item.
- **Artifact/log:** `logging/trace.jsonl`, các dòng `step = "payment_agent"`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần tính và so sánh tiền với sai số 0.10 BRL một cách tái lập.
- **Phương án cân nhắc:** `float` + `round()` hoặc helper chung dựa trên `Decimal` + `ROUND_HALF_UP`.
- **Phương án chọn:** Dùng `sum_brl()`, `round_brl()` và `within_tolerance()`.
- **Lý do:** `Decimal` tránh sai số biểu diễn nhị phân và giữ quy tắc làm tròn thống nhất giữa các agent.
- **Bằng chứng:** Cả 9 case nhiều payment row đều đối soát chính xác trong ngưỡng 0.10 BRL.

## 6. Một lỗi đã xử lý

- **Triệu chứng:** Payment ID có nguy cơ mang prefix `payment:` trong `affected_entities.payment_ids`, không khớp schema mẫu.
- **Nguyên nhân gốc:** Nhầm entity ID với evidence ID.
- **Cách xử lý:** Payment Agent trả `<order_id>:<payment_sequential>`; Coordinator chỉ thêm prefix khi tạo evidence bằng helper chung.
- **Xác minh:** `EC_030` trả các ID kết thúc bằng `:1`, `:2`, `:3`; Verifier có thể đối chiếu từng row trong payment CSV.
- **Điều học được:** Phải bám đúng contract của từng trường thay vì suy diễn từ tên helper.

## 7. Hiểu biết về luồng end-to-end

1. `main.py` đọc từng `input/EC_*.json` và lấy `claimed_order_id`.
2. Coordinator giao order cho Fulfillment Agent và Payment Agent. Hai agent đọc `DataStore` độc lập rồi bàn giao kết quả có kiểu rõ ràng.
3. Policy Agent áp dụng thứ tự: canceled, unavailable, late do seller, late do logistics, valid split payment, unsupported late claim.
4. Coordinator tạo `CaseOutput`; Payment Agent cung cấp các tổng tiền cho mọi nhánh policy.
5. Verifier kiểm tra schema, giới hạn, ID, tiền và mapping policy trước khi ghi `output/`; các handoff được ghi vào `trace.jsonl`.
6. Lần chạy cuối phải sinh đúng 50 JSON và chỉ folder `output/` được nén để nộp.

## 8. Cam kết của thành viên

- [x] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi chỉ ghi kết quả đã được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo không sao chép nguyên văn báo cáo của thành viên khác.

**Họ và tên:** Tạ Minh Đức  
**Ngày xác nhận:** 2026-08-05
