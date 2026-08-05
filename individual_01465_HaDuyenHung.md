# Member Role Report - Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                            |
| ------------------ | -------------------------------------------------------------------- |
| Họ và tên       | Hà Duyên Hùng                                                     |
| MSSV (5 số cuối) | 01465                                                                |
| Khóa/Lớp         | K3                                                                   |
| Vai trò chính    | Person C - Coordinator, Policy Agent, Verifier Agent và I/O Harness |
| Ngày hoàn thành | 2026-08-05                                                           |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                | File/hàm phụ trách                                                           | Input nhận vào                            | Output bàn giao                                               | Trạng thái |
| --------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------- | ------------ |
| Coordinator Agent                 | `src/agents/coordinator.py` - `coordinate_case()`                           | Một case JSON,`claimed_order_id`         | Handoff tới Fulfillment/Payment và nhận hai kết quả typed | Hoàn thành |
| Policy Agent                      | `src/agents/coordinator.py` - `resolve_case()`, `_choose_primary_issue()` | `FulfillmentResult`, `PaymentResult`    | `CaseOutput` đúng schema README §6                        | Hoàn thành |
| Evidence và financial resolution | `_build_evidence_ids()`, `_recommended_refund()`                            | Entity IDs, primary issue, các tổng tiền | Evidence có thể kiểm chứng và refund theo`EC_POLICY_V1` | Hoàn thành |
| Verifier Agent                    | `src/agents/verifier.py` - `verify_case()`                                  | `CaseOutput`, `DataStore`               | Danh sách lỗi; rỗng nếu case được phép ghi             | Hoàn thành |
| I/O Harness                       | `main.py` - `run_case()`, `main()`                                        | `input/EC_*.json`                         | 50 file trong`output/output/` và `logging/trace.jsonl`    | Hoàn thành |
| Tài liệu kiến trúc            | `architecture.md`                                                             | Contract và implementation của A/B/C      | Sơ đồ agent, quyền truy cập và luồng handoff            | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                          | Thành viên/module được hỗ trợ | Kết quả                                                                                                                                         |
| ------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tích hợp interface thật            | Person A -`fulfillment_agent.py`   | Coordinator gọi`analyze_fulfillment()` qua contract `FulfillmentResult`, không đọc internals của A                                       |
| Tích hợp và chuẩn hóa payment ID | Person B -`payment_agent.py`       | Nhận`PaymentResult`, chuẩn hóa `<order_id>:<payment_sequential>` và sắp sequence tăng dần                                              |
| Debug full pipeline                   | Person A và B                       | Chạy đủ 50 case, phát hiện lỗi domain qua trace từng agent và không có case bị Verifier từ chối                                      |
| Tối ưu theo phản hồi ground truth | Toàn bộ pipeline                   | Nâng tổng điểm đã xác nhận từ`93.6479` lên mức tốt nhất `95.4759` bằng cách giảm false-positive evidence và root cause thừa |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện     | File/hàm/artifact liên quan                   | Kết quả bàn giao                                                                                | Cách xác minh                                       |
| ------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Điều phối domain agents      | `coordinate_case()`                           | Mỗi case nhận đúng một`FulfillmentResult` và một `PaymentResult` trước khi áp policy | Trace có 50 bước Fulfillment và 50 bước Payment |
| Áp bảng ưu tiên policy      | `_choose_primary_issue()`                     | Đủ 6 primary issue, đúng thứ tự README §4                                                   | Audit phân bố issue trên 50 output                 |
| Tạo root cause/action/refund   | `_ranked_causes()`, `_recommended_refund()` | Một root cause/policy chính; refund payment hoặc freight theo issue                             | Kiểm tra JSON output và`verify_case()`            |
| Chặn output vi phạm hard gate | `verify_case()`                               | Kiểm tra enum, cap, evidence tồn tại, policy/action mapping, tiền và no-item rule             | `50 written, 0 failed verification`                 |
| Ghi output và trace mới nhất | `main.py`                                     | 50 JSON`EC_001` đến `EC_050`; 200 dòng trace, không append lượt cũ                      | `python main.py` và audit artifact                 |

Artifact cụ thể của lượt chạy gần nhất:

- `output/output/` có đúng 50 file từ `EC_001.json` đến `EC_050.json`.
- `logging/trace.jsonl` có 200 dòng: 50 handoff cho mỗi bước Fulfillment, Payment, Coordinator và Verifier.
- Candidate hiện tại có 183 evidence ID và vượt toàn bộ kiểm tra nội bộ. Candidate này chưa được ground-truth evaluator xác nhận tại thời điểm viết báo cáo.
- Mức điểm ground-truth cao nhất đã xác nhận là `95.4759`; tại mức này Evidence đạt `93.7829` và Root cause đạt `95.9874`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Person C là điểm tích hợp của hệ thống. Tôi phải nhận kết quả độc lập từ hai domain agent, áp một bảng policy có thứ tự ưu tiên, tạo đúng toàn bộ schema output, rồi kiểm chứng trước khi ghi file. Sai một evidence ID, vượt giới hạn danh sách, tính refund sai hoặc ghi thiếu file đều có thể làm case bị hard gate bằng 0 điểm.

### Cách triển khai

1. `coordinate_case()` lấy `claimed_order_id`, gọi `analyze_fulfillment()` và `analyze_payment()` rồi chuyển hai typed result cho `resolve_case()`.
2. `_choose_primary_issue()` duyệt rule theo đúng thứ tự: canceled, unavailable, seller late, logistics late, valid split payment, cuối cùng là unsupported late claim.
3. Primary issue được map một-một sang root cause và resolution action. Platform, seller hoặc logistics provider chỉ được gán khi bảng policy quy định có bên chịu trách nhiệm.
4. Refund của canceled/unavailable bằng tổng payment; refund của hai issue giao trễ bằng tổng freight; hai issue no-action có refund `0.0`.
5. Evidence được dựng bằng helper trong `src/shared/evidence.py`, chỉ dùng ID có thể truy ngược về CSV. Policy evidence luôn tương ứng root cause hạng 1 và được giữ khi áp giới hạn 10 ID.
6. `verify_case()` chạy cuối. Case có lỗi không được ghi ra output; lỗi vẫn được lưu trong trace để debug.
7. Confidence không quyết định classification. Policy engine quyết định issue một cách deterministic; lời gọi `gpt-4o-mini` chỉ chấm confidence và có fallback cố định nếu API lỗi.

### Input, output và contract

| Thành phần                   | Mô tả                                                                                                                                                    |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input                          | Case JSON gồm`case_id`, `customer_request.claimed_order_id`, `policy_version`                                                                       |
| Handoff đầu vào             | `FulfillmentResult` từ Person A và `PaymentResult` từ Person B theo `src/shared/interfaces.py`                                                    |
| Output                         | `CaseOutput`: assessment, affected entities, root cause, evidence, financial resolution và actions                                                      |
| Module phụ thuộc             | `fulfillment_agent.py`, `payment_agent.py`, `shared/config.py`, `shared/evidence.py`, `shared/money.py`                                          |
| Module sử dụng output        | `verifier.py` kiểm tra; `main.py` ghi JSON và trace                                                                                                  |
| Điều kiện lỗi cần xử lý | Evidence không tồn tại, enum/action/cause sai, confidence ngoài`[0,1]`, vượt cap, tiền quá 2 số lẻ, order không có item nhưng total khác 0 |

### Cách xác minh

```powershell
python -m compileall -q src main.py
git diff --check
python main.py
```

- **Kết quả mong đợi:** đọc đủ 50 input, ghi đủ 50 output, không case nào fail Verifier và trace phản ánh đủ bốn bước.
- **Kết quả thực tế:** `Found 50 input cases` và `Done: 50 written, 0 failed verification.`
- **Artifact/log:** `output/output/EC_001.json` đến `EC_050.json`; `logging/trace.jsonl` có 200 dòng.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Verifier chỉ chứng minh evidence ID tồn tại, nhưng ground truth còn phạt evidence hợp lệ mà không trực tiếp hỗ trợ kết luận.
- **Các phương án đã cân nhắc:** (1) đưa mọi order/item/payment/seller liên quan vào evidence; (2) chọn evidence theo điều kiện của từng primary issue; (3) để LLM tự chọn evidence.
- **Phương án đã chọn:** policy và evidence selection deterministic theo issue; LLM không được thêm hoặc xóa evidence.
- **Lý do:** phương án này tái lập được, tránh hallucination và tối ưu precision. Mỗi evidence đều có lý do gắn với status, timestamp, reconciliation, responsible party hoặc policy.
- **Bằng chứng quyết định phù hợp:** phiên bản evidence dàn trải có 250 ID chỉ đạt tổng `94.4646`, Evidence `87.0406`. Phiên bản chọn evidence theo issue đạt tổng tốt nhất đã xác nhận `95.4759`, Evidence `93.7829`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `valid_split_payment` từng có thêm root cause và policy evidence `DELIVERY_WITHIN_ESTIMATE`; các case không có seller chịu trách nhiệm vẫn mang seller evidence.
- **Bước tái hiện:** chạy `python main.py`, mở `output/output/EC_004.json` và kiểm tra `ranked_causes`, `evidence_ids`.
- **Nguyên nhân gốc:** Coordinator ban đầu gộp toàn bộ candidate root causes/evidence từ upstream thay vì chỉ giữ nguyên nhân tương ứng với primary issue đã thắng bảng ưu tiên.
- **Cách xử lý:** map mỗi primary issue về đúng một root cause/action; chuẩn hóa thứ tự entity ID; chỉ giữ một policy evidence; thêm `_ISSUE_POLICY` trong Verifier để bắt mismatch.
- **Cách xác minh sau khi sửa:** 50/50 case qua Verifier; Root cause tăng từ `92.2375` lên `95.9874`, Evidence tăng từ `85.3483` lên `93.7829` ở lần chấm tốt nhất.
- **Điều học được:** evidence tồn tại trong CSV mới chỉ là điều kiện cần. Evidence còn phải chính xác, liên quan trực tiếp và không tạo false-positive so với quyết định policy.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ input đến output như thế nào?**`main.py` đọc từng `input/EC_*.json`. Coordinator giao cùng `order_id` cho Fulfillment và Payment Agent. Policy Agent hợp nhất hai kết quả thành `CaseOutput`; Verifier kiểm tra trước khi harness ghi file cùng tên vào `output/output/`.
2. **Các agent handoff với nhau bằng gì?**Person A bàn giao `FulfillmentResult`, Person B bàn giao `PaymentResult`; Person C không truy cập internals của hai agent. Coordinator bàn giao `CaseOutput` cho Verifier. Các shape được định nghĩa tập trung trong `src/shared/interfaces.py`.
3. **Vì sao bảng policy phải áp theo thứ tự?**Một order có thể thỏa nhiều fact cùng lúc. Ví dụ order canceled cũng có thể có nhiều payment row. README yêu cầu canceled/unavailable thắng delivery và split payment; nếu đổi thứ tự sẽ sai issue, refund, responsible party và action.
4. **Verifier khác domain agent ở điểm nào?**Domain agent kết luận fact trong phạm vi dữ liệu của mình. Verifier không phân tích lại nghiệp vụ; nó kiểm tra contract cuối, giới hạn schema, mapping policy, evidence tồn tại và các điều kiện hard gate trước khi cho phép ghi file.
5. **Một lượt chạy được xem là thành công dựa trên artifact nào?**
   Phải có đúng 50 JSON tên khớp input, không case fail Verifier, trace mới nhất có đủ handoff, tiền/refund đúng rule và output vượt ground-truth evaluator. Verifier pass bảo đảm tính hợp lệ nội bộ; điểm ground truth mới đo độ khớp với đáp án tổ chức.

## 8. Cam kết của thành viên

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hà Duyên Hùng

**MHV:** 2A202601465
**Ngày xác nhận:** 2026-08-05
