# Nghiệm thu kỹ thuật P0–P7

**READY cho hồi quy offline trên các ứng viên đã sửa. NOT READY cho triển khai.** Ba repo đã qua kiểm thử trên nhánh sửa riêng. Workload và portal đã chạy trên loopback. Chưa có Docker/K3s/Ansible runtime hoặc GitHub hosted đủ để nghiệm thu toàn bộ luồng triển khai.

## Phiên bản giao

Tất cả commit nằm trên nhánh cục bộ `fix/p0-p7-verification` của từng repo. Bảng ghi các commit mã được kiểm. Commit tài liệu chứa báo cáo là hậu duệ trực tiếp của SHA Platform trong bảng.

| Repo | Checkpoint gốc | Ứng viên mã sau sửa | Hồi quy Python |
| --- | --- | --- | --- |
| Platform | `9a807b6bda9e8a3f25bb26dc16ca6d2acb105201` | `2261df73a4913773151dffe33932604519a9c738` | PASS 59/59 |
| Config | `59a61aa167c85b4fb29d1f6687bb9f8e485d0f07` | `7f0f7beba42d15719fef9a492f4c884616eb7a02` | PASS 61/61 |
| Workload | `626f62bdf1c3b80ddeb146e15ebf32ba6831977f` | `1384fe7f8dfe7b4f39b9265ff5fe2761669ebd60` | PASS 16/16 |

**Terraform PASS 113/113 mock plan và 7/7 ca bootstrap Python riêng.** Profile B có một server và một worker mặc định, tăng thêm worker thứ hai bằng biến đã kiểm. Hai ca 63/64 ký tự được bổ sung. Không có dữ liệu xác nhận ba node đang chạy. Baseline R1 trên đúng ba SHA có 111 mock, bootstrap 7/7 và Python 52/55/15.

- **Config/CICD.** Cùng một verifier render dùng cho image promotion, rollback và chart/values thay đổi. Đã kiểm các chế độ NetworkPolicy/HPA/quota. Đường đề xuất image-only dùng App token và khóa base, mặc định đóng. Đã test cố định file, compare-and-swap, freeze, stale base, branch khác nội dung và retry. Hosted workflow chưa kích hoạt. Hai workflow Workload vẫn hard-disabled, Config vẫn `frozen: true`.
- **Portal/placement.** Dùng requests từ commit Git immutable, snapshot quan sát phải khớp revision, Argo comparison phải khớp lúc submit. Có giới hạn capacity khi rollback. Nếu GitHub trả PR nhưng audit lỗi, trả lại cùng đề xuất để đối chiếu. Hai merge order dùng đường PR hiện hành. Dữ liệu metrics/resource được chuẩn hóa từ export, không truy vấn cluster khi chạy assembler.
- **Workload/runtime.** HTTP loopback Workload đạt `/`, `/healthz`, `/metrics`. Portal HTTPS loopback đạt đăng nhập qua token endpoint thử nghiệm, JWT claims fixture trên kênh TLS, PKCE, cookie, viewer deny và replay deny. Không kiểm Gunicorn/container Linux, IdP thật, Argo thật hoặc GitHub App thật.
- **Hiệu năng.** CBC và exhaustive cùng 0,724 trên snapshot fixture, greedy 0,738. Baseline CSV cho 0,026667 so với 0,028800 đơn vị giá mô phỏng. Đây là kết quả trên dữ liệu fixture, không suy ra hóa đơn AWS.

[Tái lập và kết quả](TEST_RESULTS.md) · [Kế hoạch](TEST_PLAN.md) · [Sổ lỗi](DEFECT_REGISTER.md) · [Đánh giá gốc](INDEPENDENT_FINAL_REVIEW.md)

## Ca còn chặn

- **BLOCKED.** Docker CLI có mặt nhưng daemon named pipe không đáp ứng. WSL trả `E_ACCESSDENIED`. k3d, Ansible, ansible-lint, Trivy, Gitleaks, actionlint, k6, promtool và Alloy không có trên PATH. Hai gói Helm upstream tải qua HTTPS đều exit 7. Không đổi dịch vụ host, tải phần mềm hệ thống hoặc mượn cluster đang chạy.
- **NOT RUN.** Kubernetes/Argo drift, private TLS ingress sau khi cài controller, load/HPA, drain, khôi phục K3s thật, telemetry end-to-end, resource overhead và bảo mật container. SQLite phục hồi giả lập và policy/render offline đã chạy.
- **OPEN.** R1-12 cần base OCI digest được xác minh, dependency hashes cho Linux và build/scan image exact. Gói upstream có thể render phần phụ trợ sau khi cung cấp artefact cục bộ đã duyệt. Snapshot observed thật cần export từ cluster đã duyệt và RTT/cost có nguồn. Audit retention và xác thực GHCR read là gate riêng.
- **NOT RUN theo quyền.** AWS, remote backend và real provider, hosted GitHub/GHCR, deploy và publication. Phải có xác nhận owner và runbook tương ứng. [Gate AWS](MANUAL_AWS_GATES.md) · [Promotion runbook](PROMOTION_RUNBOOK.md)

## Readiness

| Hạng mục | Verdict | Bằng chứng hoặc điều kiện |
| --- | --- | --- |
| Source code correctness | **READY** trong phạm vi đường code và đồng bộ contract sửa được offline | Ca lỗi chính đã pass trên cùng phạm vi. R1-12, TLS runtime, quyền hosted và vận hành giữ trạng thái riêng. |
| Offline regression | **READY** | 113 Terraform mock, bootstrap 7, Python 59/61/16, lint và policy Helm. |
| Local runtime | **NOT READY** | Hai HTTP smoke loopback pass. Linux container, Ansible và K3s bị chặn. |
| Local end-to-end integration | **NOT READY** | Mock request→GitOps patch→Helm kiểm được. Chưa có cluster/Argo/telemetry/failure chain. |
| Hosted CI/CD | **NOT READY** | Chưa kiểm App identity/check publisher, runner build, registry quyền đọc và approval gate. Publication/preview tiếp tục tắt. |
| AWS deployment | **NOT READY** | Chưa có gate owner, plan thật, IAM/AMI/SSM/backend, chi phí hay cluster runtime. |
| Portfolio demonstration | **NOT READY** cho demo end-to-end | Có dữ liệu offline, mock, benchmark và loopback để minh họa riêng với nhãn phạm vi. |
| Production readiness | **NOT READY** | Hạ tầng một AZ/server, secure image build và scan, quyền, quan sát tải/SLO và recovery thực chưa đủ bằng chứng. |

## Bản nháp PR nội bộ song ngữ

### English

**Platform** — Align Terraform placement labels with Kubernetes, bind portal authorization and feasibility to an immutable Config revision, recover the same proposal after audit confirmation failure, and assemble sanitized observed snapshots. Review resource parsing, rollback feasibility, idempotency and the owner-only manual gates.

**Config** — Verify allowed optional Helm resources during promotion and rollback, add a gated image-only App proposal CLI and isolate optional read-only GHCR credentials to the protected verification job. Review first pin and admission, exact scope, GitHub App attribution, package permissions, and default-disabled behavior.

**Workload** — Require Flask runtime tests in the PR job and pin the setup action. Publication and preview hard stops remain in place. Review the explicit dependencies and fail-closed tests.

**Validation and risk** — 113 Terraform mocks, 7 backend checks and Python suites 59/61/16 passed. Helm and loopback HTTP/TLS passed. Docker/K3s, hosted and AWS controls remain unverified. Recheck protected base refs before authorized hosting. A local revert can target each scoped commit. For any live revert, use the material gates and runtime evidence. [Test evidence](TEST_RESULTS.md)

### Tiếng Việt

**Platform** — Đồng bộ nhãn Terraform với Kubernetes, ràng buộc quyền và tính khả thi của portal vào một revision Config, giữ cùng đề xuất khi lỗi xác nhận audit, và tạo snapshot quan sát từ export đã làm sạch. Review parser tài nguyên, rollback, tính lặp an toàn và các gate owner.

**Config** — Xác minh tài nguyên Helm tùy chọn khi promotion và rollback, bổ sung CLI App đề xuất chỉ đổi ảnh và cô lập thông tin đọc GHCR tùy chọn trong job bảo vệ. Review lần pin đầu, admission, phạm vi chính xác, danh tính GitHub App, quyền package và mặc định đóng.

**Workload** — Bắt buộc test Flask trong job PR và pin Action setup. Giữ hard stop publication và preview. Review dependency rõ và ca fail-closed.

**Kiểm thử và rủi ro** — Đạt 113 Terraform mock, 7 backend và Python 59/61/16. Helm và loopback HTTP/TLS đạt. Docker/K3s, hosted và AWS chưa có xác minh. Đối chiếu lại base trước khi được phép làm hosted. Có thể revert theo từng commit cục bộ. Với thay đổi live, dùng gate và bằng chứng runtime tương ứng. [Bằng chứng](TEST_RESULTS.md)

Không thao tác AWS, phát hành ảnh, mở PR thật, push, merge hoặc đổi cài đặt GitHub. Giữ nguyên các checkout gốc, refs và recovery worktrees. Các thay đổi mã và tài liệu được ghi trên nhánh ứng viên cục bộ. Đối chiếu cuối giữ checkout gốc Platform tại `9a807b6`, Config tại `9564111` và Workload tại `e21e077`, với index trống và các thay đổi gốc vẫn hiện diện. Candidate Config `59a61aa` và Workload `626f62b` cũng giữ nguyên trên các worktree review đã có.
