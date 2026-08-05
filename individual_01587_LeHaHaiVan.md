# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                              |
| --------------- | ------------------------------------------------------ |
| Họ và tên       | Lê Hà Hải Vân                                          |
| MSSV            | 2A202601587                                            |
| Khóa/Lớp        | K3                                                      |
| Vai trò chính   | Order & Seller Agent + Delivery Agent (Fulfillment) |
| Ngày hoàn thành | 2026-08-05                                              |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Order & Seller Agent + Delivery Agent | `src/agents/fulfillment_agent.py` — `analyze_fulfillment()` | `order_id` (từ `customer_request.claimed_order_id`) | `FulfillmentResult`: `order_status`, `delivered_late`, `seller_late`, `late_seller_ids`, `candidate_root_causes`, `order_ids`/`item_ids`/`seller_ids` | Hoàn thành |
| Tài liệu kiến trúc cho agent của mình | `architecture.md` — mục "Order & Seller Agent + Delivery Agent" | Code thực tế đã chạy | Mô tả vai trò, input/output, quyền truy cập dữ liệu, quyết định gộp 2 agent thành 1 hàm | Hoàn thành |

Cả hai deliverable đều đã chạy thực tế trên 50 case thật trong `input/`, không phải dữ liệu giả lập.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả và bằng chứng |
| --- | --- | --- |
| Review + fix bug format ID | Person B — `src/agents/payment_agent.py` | Phát hiện `payment_ids` bị gắn nhầm prefix `payment:` (đúng ra phải là ID trần `<order_id>:<seq>` theo README.md #6, prefix chỉ dùng cho `evidence_ids`). Sửa trực tiếp trên branch `PersonB`, verify lại bằng cách chạy `analyze_payment()` trên 3 case thật, xác nhận output đúng định dạng. |
| Review + fix logic dư thừa | Person C — `src/agents/coordinator.py` | Phát hiện `evidence_ids` luôn chèn `seller:<id>` kể cả khi seller không phải responsible party (34/50 case), và `ranked_causes` luôn chèn thêm nguyên nhân phụ không liên quan đến `primary_issue` (toàn bộ 9 case `valid_split_payment`). Sửa cả hai, verify bằng script kiểm tra toàn bộ 50 case output. Điểm leaderboard tăng từ 93.6479 lên 95.1407 sau fix này. |
| Merge nhánh tích hợp | Merge `Hung` vào `Van` | Merge sạch, không conflict; chạy lại `main.py` xác nhận 50/50 case pass verification sau merge. |
| Bổ sung tài liệu còn thiếu | `architecture.md` — mục Coordinator/Policy Agent + Verifier Agent + sơ đồ tổng | Person C chưa viết phần này theo phân công ban đầu; viết lại dựa trên code thực tế đã merge để tài liệu khớp với hành vi thật của hệ thống. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Implement `analyze_fulfillment()` áp dụng đúng thứ tự ưu tiên README.md #4 | `src/agents/fulfillment_agent.py` | Trả về `FulfillmentResult` cho mọi order_id trong 50 case thật, không lỗi | `python -m py_compile src/agents/fulfillment_agent.py`; chạy qua toàn bộ `input/EC_*.json` |
| Xử lý case order không có item row | `analyze_fulfillment()` | `item_ids`/`seller_ids` trả về rỗng đúng theo README.md #6 | Xác nhận thực tế: 8 order có `order_status = unavailable` trong data thật đều có 0 dòng trong `order_items.csv`, output rỗng đúng như kỳ vọng |
| Kiểm chứng phân bố root cause trên toàn bộ 50 case | Script kiểm tra ad-hoc trên `analyze_fulfillment()` | 18 `DELIVERY_WITHIN_ESTIMATE`, 8 `SELLER_HANDOFF_AFTER_LIMIT`, 8 `ORDER_CANCELED_AFTER_PAYMENT`, 8 `ORDER_UNAVAILABLE_AFTER_PAYMENT`, 8 `CARRIER_DELIVERED_AFTER_ESTIMATE` — mỗi case có đúng 1 candidate, không có case mơ hồ | Script Python duyệt qua toàn bộ 50 file `input/`, gọi `analyze_fulfillment()`, in phân bố |
| Fix bug evidence/root-cause thừa ở Coordinator (hỗ trợ Person C) | `src/agents/coordinator.py` | Điểm "Bằng chứng" và "Nguyên nhân gốc" — hai hạng mục thấp nhất — được cải thiện | So sánh output trước/sau fix cho cả 50 case, xác nhận `primary_issue`/`financial_resolution` không đổi, chỉ evidence/root-cause bớt nhiễu |

Output cụ thể: `src/agents/fulfillment_agent.py::analyze_fulfillment()` là nguồn duy nhất cung cấp `order_status`, `delivered_late`, `seller_late` cho Coordinator — nếu hàm này sai, `primary_issue` của toàn bộ pipeline sẽ sai theo vì Coordinator không tự tính lại các giá trị này.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi trả lời 3 câu hỏi nghiệp vụ cho mỗi case: (1) đơn có bị hủy/không còn hàng không, (2) seller có bàn giao hàng cho carrier trễ hơn `shipping_limit_date` của item hay không, (3) carrier có giao hàng đến khách trễ hơn `order_estimated_delivery_date` hay không. Đây là bước đầu tiên trong pipeline — Coordinator không đọc CSV trực tiếp, nên nếu phần này tính sai thì toàn bộ quyết định `primary_issue`, `responsible_parties` phía sau đều sai theo.

### Cách triển khai

Áp dụng đúng bảng ưu tiên trong README.md #4 theo dạng if/elif tuần tự: `canceled` → `unavailable` → (giao trễ + seller trễ) → (giao trễ + seller đúng hạn) → (giao đúng hạn). Với order có nhiều item, seller bị coi là trễ nếu **bất kỳ item nào** của seller đó có `order_delivered_carrier_date > shipping_limit_date` (so sánh string ISO trực tiếp vì Olist dùng định dạng `YYYY-MM-DD HH:MM:SS` cố định, so sánh lexicographic tương đương so sánh thời gian). Kết quả trả về không phải `primary_issue` cuối cùng, mà là `candidate_root_causes` — Coordinator vẫn cần kết hợp thêm `PaymentResult.payment_total_brl` để xác nhận điều kiện "đã thanh toán" cho case `canceled`/`unavailable`, vì Fulfillment Agent không có quyền truy cập dữ liệu payment.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `order_id: str` (chuỗi `claimed_order_id` lấy từ `customer_request` trong file input) |
| Output | `FulfillmentResult` (TypedDict trong `src/shared/interfaces.py`): `order_exists`, `order_status`, `order_ids`, `item_ids`, `seller_ids`, `estimated_date`, `actual_carrier_date`, `actual_customer_date`, `delivered_late`, `seller_late`, `late_seller_ids`, `candidate_root_causes` |
| Module phụ thuộc | `src/shared/data_loader.py` (`get_data_store()` — đọc + cache `orders.csv`, `order_items.csv`) |
| Module sử dụng output | `src/agents/coordinator.py` (`coordinate_case()`/`resolve_case()`) |
| Điều kiện lỗi cần xử lý | `order_id` không tồn tại trong `orders.csv` → trả `order_exists=False`, mọi list rỗng; order tồn tại nhưng không có dòng nào trong `order_items.csv` (case `unavailable` thực tế) → `item_ids`/`seller_ids` rỗng theo đúng README.md #6 |

### Cách xác minh

```bash
python -m py_compile src/agents/fulfillment_agent.py
python main.py
```

- **Kết quả mong đợi:** biên dịch không lỗi; toàn bộ 50 case trong `input/` được xử lý, không case nào bị Verifier từ chối.
- **Kết quả thực tế:** `Found 50 input cases` / `Done: 50 written, 0 failed verification.` — khớp kỳ vọng.
- **Artifact/log:** `output/EC_001.json` … `EC_050.json`, `logging/trace.jsonl` (4 dòng trace/case: fulfillment_agent, payment_agent, coordinator, verifier).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** README gợi ý kiến trúc tách riêng "Order & Seller Agent" và "Delivery Agent" thành hai agent khác nhau. Cả hai đều cần cùng một dữ liệu nguồn: `orders.csv` (status, các mốc ngày) và `order_items.csv` (`shipping_limit_date`, `seller_id`) cho cùng một `order_id`.
- **Các phương án đã cân nhắc:**
  1. Giữ hai hàm/agent riêng biệt như gợi ý, mỗi hàm tự gọi `get_data_store()` và tự lọc lại `order_items` theo `order_id`.
  2. Gộp thành một hàm `analyze_fulfillment()` duy nhất, join dữ liệu một lần rồi tính cả seller-timing lẫn delivery-timing trong cùng một lượt.
- **Phương án đã chọn:** Phương án 2 — một hàm duy nhất.
- **Lý do:** Hai trách nhiệm dùng chung một tập dòng dữ liệu (`get_items(order_id)` join `order_items` theo `order_id`); tách thành hai lời gọi độc lập nghĩa là join lại cùng dữ liệu hai lần cho mỗi case mà không thu được lợi ích gì — không có ranh giới quyền truy cập hay logic nghiệp vụ nào cần cách ly giữa hai phần này. Việc tách chỉ có ý nghĩa nếu chúng cần các nguồn dữ liệu khác nhau hoặc có thể chạy song song trên hạ tầng khác nhau, cả hai điều đó đều không đúng ở đây.
- **Bằng chứng quyết định phù hợp:** Toàn bộ 50 case chạy qua `analyze_fulfillment()` cho kết quả nhất quán, không case nào bị Verifier từ chối; thời gian chạy toàn bộ pipeline (bao gồm cả gọi LLM cho confidence) chỉ khoảng 48 giây cho 50 case, không có dấu hiệu nghẽn do việc gộp hàm.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Sau khi Person B và Person C hoàn thành phần việc, điểm leaderboard ban đầu là `Tổng điểm: 93.6479`, trong đó hai hạng mục thấp rõ rệt so với phần còn lại: `Bằng chứng: 85.3483` và `Nguyên nhân gốc: 92.2375` (các hạng mục khác đều 95-96).
- **Lệnh hoặc bước tái hiện:** Viết script Python duyệt qua `output/EC_*.json`, gom nhóm theo `primary_issue`, in ra thành phần `evidence_ids` (theo loại prefix) và độ dài `ranked_causes` cho từng nhóm.
- **Nguyên nhân gốc:**
  1. `src/agents/coordinator.py` luôn chèn `seller:<seller_id>` vào `evidence_ids` cho **mọi** case có item, bất kể `primary_issue` có quy trách nhiệm cho seller hay không. Theo README.md #4, seller chỉ là responsible party trong case `late_delivery_seller`; 4/6 loại `primary_issue` còn lại có responsible party là `platform`/`logistics_provider`/không có — nên trích seller làm bằng chứng ở đó không hỗ trợ cho kết luận, chỉ gây nhiễu. Thực tế bug này xuất hiện ở 34/50 case.
  2. `ranked_causes` luôn cộng thêm `candidate_root_causes` của Fulfillment Agent và cờ split-payment vào danh sách nguyên nhân, bất kể nó có phải lý do thật của `primary_issue` hay không. Ví dụ: toàn bộ 9 case `valid_split_payment` bị gắn thêm nguyên nhân phụ `DELIVERY_WITHIN_ESTIMATE` — đúng là sự thật về đơn hàng, nhưng không liên quan đến lý do "vì sao đây là split payment hợp lệ".
- **Cách xử lý:** Sửa `_build_evidence_ids()` để chỉ thêm seller evidence khi `primary_issue == 'late_delivery_seller'`; sửa `_ranked_causes()` để chỉ trả về đúng một `cause_code` ứng với `primary_issue` (bảng README.md #4 vốn là ánh xạ 1:1, và README nêu rõ bộ 50 case chính thức không có tình huống nhiều nguyên nhân mơ hồ).
- **Cách xác minh sau khi sửa:** Chạy lại `python main.py`, script kiểm tra xác nhận 0/50 case còn seller evidence sai vị trí và 0/50 case còn nhiều hơn 1 ranked cause; đối chiếu `primary_issue` và `financial_resolution` của cả 50 case trước/sau fix — không thay đổi (chỉ evidence/root-cause bớt nhiễu, không ảnh hưởng quyết định nghiệp vụ). Sau khi nộp lại: `Tổng điểm: 95.1407`, `Bằng chứng: 94.6470`, `Nguyên nhân gốc: 95.6577`.
- **Điều học được:** Khi output cho phép "tối đa N phần tử" (ở đây tối đa 3 root cause, 10 evidence), càng nhiều chưa chắc càng tốt — thêm một sự thật đúng nhưng không liên quan đến kết luận vẫn có thể bị tính là nhiễu/giảm độ chính xác, vì đề bài đánh giá bằng chứng và nguyên nhân theo mức độ hỗ trợ trực tiếp cho `primary_issue`/`responsible_parties`, không phải theo số lượng thông tin đúng liệt kê được.

## 7. Hiểu biết về luồng end-to-end

> Lưu ý: 5 câu hỏi gốc trong mẫu báo cáo này (Crossref, vector index, retrieval/answer quality, freshness monitoring, baseline/corrupted/repaired) thuộc về một bài lab RAG khác, không khớp với bài lab thực tế của nhóm (Multi-Agent E-commerce Dispute Resolution trên dữ liệu Olist). Tôi trả lời lại đúng luồng end-to-end của bài lab thực tế thay vì chép nguyên câu hỏi không áp dụng được.

**Câu trả lời:**

1. **Dữ liệu đi từ đâu đến đâu?** Từ 9 file CSV trong `data/` (Olist Brazilian E-commerce) → `src/shared/data_loader.get_data_store()` load và cache một lần (index theo `order_id`, group theo `order_id` cho items/payments) → hai agent domain (`analyze_fulfillment`, `analyze_payment`) đọc qua `DataStore`, không đọc CSV trực tiếp → `coordinator.resolve_case()` kết hợp hai kết quả áp dụng `EC_POLICY_V1` → `verifier.verify_case()` kiểm tra hard-gate → `main.py` ghi ra `output/EC_*.json`.
2. **Test set và "đáp án đúng" dùng để đánh giá là gì?** Không có ground-truth document ID như bài RAG; "đáp án đúng" ở đây là bảng luật nghiệp vụ cố định trong README.md #4 (mapping `primary_issue` → `root_cause_code` → `responsible_party` → `refund` → `action`) áp dụng cho từng case trong 50 file `input/EC_001.json`…`EC_050.json`. Đánh giá đúng/sai dựa trên so khớp với chính bảng luật này, không phải một tập nhãn được gán thủ công.
3. **Quality checks nào khác ngoài việc chỉ tin dữ liệu đầu vào?** `verifier.verify_case()` là lớp kiểm tra độc lập cuối cùng: xác nhận `primary_issue`/`case_status` nằm trong enum hợp lệ, `confidence` trong `[0,1]`, mọi list không vượt giới hạn số lượng, và quan trọng nhất là `validate_evidence_ids()` — xác nhận từng evidence ID **thực sự tồn tại** trong CSV gốc, không tự bịa ra order/item/seller không có thật (README.md #5 gọi đây là false positive).
4. **Vì sao phải chạy đúng 50 case cố định thay vì tự tạo thêm case để test?** Vì bảng chấm điểm (README.md #8) tính trên đúng 50 case `EC_001`–`EC_050`, và các quy tắc join/tính tiền phải cho ra kết quả giống hệt nhau mỗi lần chạy lại (không có yếu tố ngẫu nhiên trong phần rule-based) — nếu đổi tập test, không thể so sánh được liệu một thay đổi code có thực sự cải thiện độ chính xác hay chỉ đổi hành vi trên case khác.
5. **Một thay đổi được xem là "sửa đúng" dựa trên gì?** Dựa trên hai điều kiện cùng lúc: (a) không có case nào bị `verifier.verify_case()` từ chối (0 hard-gate failure), và (b) `primary_issue`/`financial_resolution` của từng case trong 50 case không đổi so với trước khi sửa nếu thay đổi đó chỉ nhắm vào evidence/root-cause — tức là phải chứng minh được thay đổi không vô tình phá vỡ phần logic nghiệp vụ đã đúng trước đó, chứ không chỉ nhìn điểm tổng tăng lên.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Hà Hải Vân
**Ngày xác nhận:** 2026-08-05
