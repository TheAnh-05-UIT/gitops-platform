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
| R1-08 | MEDIUM | PASS lab TLS | k3d dùng Traefik riêng của lab, TLS xác minh qua cert lab, route GET / trả workload identity. Hạ tầng AWS giữ gate riêng. |
| R1-09 | MEDIUM | PASS lab observed | Snapshot lấy Node/Pod và NodeMetrics từ kube API, gắn revision Argo local. Browser preview qua snapshot, CBC Optimal 5/5. Dữ liệu vị trí và latency chỉ áp dụng cho lab. Không có pricing. |
| R1-10 | MEDIUM | PASS offline | Platform `tests/test_promotion_placement_contract.py` chạy `prepare_change` và `submit_change` qua test double, theo dõi PUT thật và hai merge order bằng Git tạm. Bỏ đường UUID cũ không còn caller. |
| R1-11 | LOW | PASS scope chính | Platform đưa thiết kế AWS và ADR 0003/0004 vào worktree ứng viên, đánh dấu tài liệu baseline và nối với nghiệm thu hiện tại. Giữ nguyên bản gốc dở dang. |
| R1-12 | LOW | PASS linux/amd64 reproducibility inputs | Workload `b0ddbba` pin OCI digest và khóa chín gói runtime có SHA256 từ PyPI. Build hash-lock, scan và SBOM thực thi trên đúng artefact. Kết quả release security theo R2-05. |

## Ca khác phát hiện trong vòng sửa

- **R2-01 · MEDIUM · Workload.** Bản sửa đầu dùng pin Action thiếu ký tự trong `.github/workflows/ci.yml`. Test liên repo từ chối; đã đối chiếu commit đầy đủ của phiên bản 6.2.0 và sửa pin. Kiểm tra 40 ký tự ở cả ba ứng viên đạt. [Release setup-python](https://github.com/actions/setup-python/releases/tag/v6.2.0)
- **R2-02 · INFORMATIONAL · Môi trường.** Docker CLI không kết nối daemon, WSL access denied, thiếu k3d/Ansible và scanner. Tái hiện bằng client-only version và công cụ liệt kê. Chặn container, Ansible và Kubernetes runtime. Không khởi động lại dịch vụ hoặc thay đổi cấu hình host.

## R2 Local Runtime

| Mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| Template Ansible dùng đường dẫn tương đối | **FAIL** trên ứng viên, **PASS** sau sửa `8b7886e15c65c3887d1c658bb0922d5c4c8d7bae` | Lint 26.11.1 chặn hai `no-relative-paths` ở `k3s-node.yml`, `k3s-start.yml`. Neo nguồn template vào thư mục playbook. Regression kiểm tra cả hai đường dẫn mở được. Sau sửa syntax 2/2, test 8/8 và lint sạch. |
| R1-12 | **PASS reproducibility inputs** | OCI index, Linux manifest, PyPI hashes, build Linux, SBOM và scan đã có bằng chứng. |
| R1-08, R1-09 | **PASS trong lab** | TLS ingress và metrics Node/Pod thật có bằng chứng, URL Git được cung cấp trong lab. |
| Truy cập của phiên R2 | **PASS sau restart** | Docker daemon, HTTPS, bind loopback và ba worktree ghi được. WSL PowerShell phải chạy qua cơ chế xin quyền. |
| R2-03 · Alertmanager route | **FAIL → PASS** | Operator từ chối `undefined receiver "null" used in route` khi Helm kế thừa nested route. Config `dfd3486` khai báo `routes: []`, render và ca regression đạt. StatefulSet Ready và nhận alert do Prometheus gửi. |
| R2-04 · Alloy CRI log framing | **FAIL → PASS** | Alloy follow Pod logs nhưng trước sửa mọi dòng bị lọc, Loki trả 0. Config `b235d28` nhận CR/LF cuối dòng trong bộ lọc và regex nhưng chỉ ghi sự kiện allowlist đã trích xuất. Regression, Alloy validate và mẫu 20 sự kiện Loki đạt. |
| R2-05 · Workload base OS vulnerability | **FAIL → PASS linux/amd64** | Trixie 54 HIGH. Bookworm 100 HIGH và 2 CRITICAL. Workload `1fa207e` chuyển sang Alpine được pin, khóa musllinux hashes và pin `krb5-libs=1.22.3-r0`. Ảnh build lại qua Trivy với 0 HIGH, 0 CRITICAL, 0 secret và có SBOM. |
| R2-06 · Ansible full runtime | **BLOCKED disk** | Đã vượt lỗi overlayfs lồng trong Docker bằng drop-in native riêng của lab. Server và một worker Ready. Dừng sớm ở khoảng 16,80 GiB trống khi worker thứ hai khởi động, trước lượt idempotency đầy đủ. |

[Xem ma trận nghiệm thu và lệnh tái lập](LOCAL_RUNTIME_ACCEPTANCE.md)
