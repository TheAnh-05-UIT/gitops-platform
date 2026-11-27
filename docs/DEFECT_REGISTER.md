# Sổ lỗi và bằng chứng sửa lỗi

Vị trí gốc, mức độ, tác động và tái hiện chi tiết của R1 ghi trong [review độc lập](INDEPENDENT_FINAL_REVIEW.md). Bảng dưới bổ sung trạng thái trên nhánh sửa và điều kiện còn lại.

| ID | Mức | Trạng thái | Sửa và kiểm lại |
| --- | --- | --- | --- |
| R1-01 | HIGH | PASS offline | Config `scripts/check_promotion.py` dùng cùng immutable render verifier cho promotion, rollback và values thay đổi. Kiểm exact apiVersion/kind/name/namespace, container duy nhất và Pod policy. Ca NetworkPolicy/HPA/quota trước đó fail nay qua trong `tests/test_digest_compatibility.py`. App dùng tracked values, không override Helm ngoài Git. |
| R1-02 | HIGH | PASS offline | Platform `portal/app.py` và `portal/github_client.py` lấy requests từ immutable Git base, kiểm observed revision, Argo comparison SHA và khả năng rollback ở vùng cũ. Ca 2000 mCPU trả 422. Thêm ca duplicate/ambiguous YAML trong `tests/test_portal_proposals.py`. |
| R1-03 | HIGH | PASS với test doubles; BLOCKED hosted | Config `scripts/submit_promotion.py` và `tests/test_promotion_writer.py`. Owner CLI mới kiểm admission, receipt, registry bytes, branch/image-only và compare-and-swap. Hai lớp opt-in. Không gắn Actions, xác thực GitHub App thật chưa chạy. |
| R1-04 | MEDIUM | PASS tĩnh; BLOCKED private GHCR | Config `.github/workflows/trusted-promotion.yml` có phân quyền credential read riêng và Docker config tạm trong protected job. Script bỏ token App khỏi môi trường Buildx. Không đọc secret hoặc GHCR của dự án. |
| R1-05 | MEDIUM | PASS offline | Workload `.github/workflows/ci.yml` pin Python action, cài runtime deps, giữ PyYAML. Bỏ skip thiếu Flask trong `tests/test_red_metrics.py`. Baseline thiếu Flask skip hai ca, ứng viên sửa bắt buộc hai ca. Hosted vẫn chưa thực thi. |
| R1-06 | MEDIUM | PASS offline | Platform `lab/variables.tf` và `modules/ansible-inventory/variables.tf` cùng kiểm 63 ký tự như adapter. Hai ca HCL biên, lab lên 51/51 và cả runner 113/113. |
| R1-07 | MEDIUM | PASS offline | Platform `portal/app.py` phân biệt intent chưa ghi và confirm lỗi sau khi có PR. Test mock fsync fail thấy HTTP 503 kèm PR và proposal cùng ID để đối chiếu, journal có timestamp. Retained audit là gate triển khai. |
| R1-08 | MEDIUM | BLOCKED TLS cluster | Config `apps/workload-api/README.md` ghi rõ K3s bootstrap tắt Traefik và ServiceLB, port-forward là đường demo mặc định. Controller/private listener/TLS là lựa chọn đã review riêng. Chưa có runtime kubeconfig cô lập. |
| R1-09 | MEDIUM | PASS fixture; BLOCKED observed runtime | Platform `optimizer/snapshot_capture.py` dùng exports offline, chuẩn hóa NodeMetricsList, bỏ annotation/env, ghép topology vật lý nếu có inventory và gắn Config revision. Test duplicate/future metrics, mode giả lập và redaction. RTT/cost vẫn do operator phê duyệt, không tự truy vấn Prometheus. |
| R1-10 | MEDIUM | PASS offline | Platform `tests/test_promotion_placement_contract.py` chạy `prepare_change` và `submit_change` qua test double, theo dõi PUT thật và hai merge order bằng Git tạm. Bỏ đường UUID cũ không còn caller. |
| R1-11 | LOW | PASS scope chính | Platform đưa thiết kế AWS và ADR 0003/0004 vào worktree ứng viên, đánh dấu tài liệu baseline và nối với nghiệm thu hiện tại. Giữ nguyên bản gốc dở dang. |
| R1-12 | LOW | OPEN, BLOCKED container | Workload `Dockerfile:1–6` và `requirements.txt:1–2` vẫn dùng tag base và version ranges. Cần pin digest đã duyệt và khóa hashes có thể chạy trên Linux, sau đó build/scan exact image. Không thay deps với digest/hashes chưa xác minh. Chặn reproducibility production. |

## Ca khác phát hiện trong vòng sửa

- **R2-01 · MEDIUM · Workload.** Bản sửa đầu dùng pin Action thiếu ký tự trong `.github/workflows/ci.yml`. Test liên repo từ chối; đã đối chiếu commit đầy đủ của phiên bản 6.2.0 và sửa pin. Kiểm tra 40 ký tự ở cả ba ứng viên đạt. [Release setup-python](https://github.com/actions/setup-python/releases/tag/v6.2.0)
- **R2-02 · INFORMATIONAL · Môi trường.** Docker CLI không kết nối daemon, WSL access denied, thiếu k3d/Ansible và scanner. Tái hiện bằng client-only version và công cụ liệt kê. Chặn container, Ansible và Kubernetes runtime. Không khởi động lại dịch vụ hoặc thay đổi cấu hình host.

## R2 Local Runtime

| Mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Template Ansible dùng đường dẫn tương đối | **FAIL** trên ứng viên, **PASS** sau sửa `8b7886e15c65c3887d1c658bb0922d5c4c8d7bae` | Lint 26.11.1 chặn hai `no-relative-paths` ở `k3s-node.yml`, `k3s-start.yml`. Neo nguồn template vào thư mục playbook. Regression kiểm tra cả hai đường dẫn mở được. Sau sửa syntax 2/2, test 8/8 và lint sạch. |
| R1-12 | **OPEN / BLOCKED** | Tái hiện từ Dockerfile và requirements ứng viên. Docker socket bị từ chối và registry/PyPI không phân giải được từ phiên Codex. Chưa khóa digest/hash hoặc xác minh build Linux. |
| R1-08, R1-09 | **BLOCKED runtime** | Chưa có TLS ingress và chưa quan sát placement từ số liệu Kubernetes thực. |
| Truy cập của phiên R2 | **BLOCKED** | Docker socket và TCP bind trả EPERM, truy vấn netlink bị từ chối, tải HTTPS thất bại ở DNS. Ansible ping localhost báo local RPC server không khởi động. Bằng chứng này áp dụng cho tiến trình trong phiên, không xác định lỗi dịch vụ trên host. |

[Xem ma trận nghiệm thu và lệnh tái lập](LOCAL_RUNTIME_ACCEPTANCE.md)
