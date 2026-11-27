# R2 — Nghiệm thu runtime cục bộ

**Kết luận ngày 2026-11-27 — BLOCKED. Chưa đủ bằng chứng để chuyển sang R3 Hosted Integration.** Kiểm tra Ansible syntax, inventory và lint đã đạt sau một bản sửa cục bộ. Tiến trình Codex bị từ chối khi kết nối Docker và mở cổng loopback, đồng thời không phân giải được các máy chủ chứa artifact. Chuỗi build → scan → GitOps → phục vụ → giám sát → phục hồi → rollback vẫn chưa được nghiệm thu. R1-12 còn mở.

## Phiên bản được kiểm tra

Ba worktree cục bộ nằm dưới `.r2-candidates/<repo>` trên nhánh `chore/r2-local-runtime` riêng của từng repo.

| Repo | Ứng viên R1 | SHA mã nguồn cuối được kiểm tra ở R2 |
| --- | --- | --- |
| Platform | `5a5f7207efac446bbc97862c495c437626c1c63d` | `8b7886e15c65c3887d1c658bb0922d5c4c8d7bae` |
| Config | `7f0f7beba42d15719fef9a492f4c884616eb7a02` | `7f0f7beba42d15719fef9a492f4c884616eb7a02` |
| Workload | `1384fe7f8dfe7b4f39b9265ff5fe2761669ebd60` | `1384fe7f8dfe7b4f39b9265ff5fe2761669ebd60` |

`git rev-parse --verify '<sha>^{commit}'` và `git for-each-ref --contains <sha>` xác nhận cả ba commit và nhánh phục hồi `fix/p0-p7-verification`. `git worktree list --porcelain` trên Linux hiển thị các đường dẫn Windows trong Temp là `prunable`. Thư mục phục hồi tồn tại trên ổ C. Worktree R2 được tạo bằng `git worktree add -b chore/r2-local-runtime <đường-dẫn-mới> <sha>`, giữ các worktree, metadata phục hồi và thay đổi gốc. Commit chứa báo cáo này truy xuất bằng `git log -1 --format=%H -- docs/LOCAL_RUNTIME_ACCEPTANCE.md`.

## R2.0 và R2.1 — Môi trường và artifact

| Kiểm tra | Kết quả quan sát trong phiên Codex |
| --- | --- |
| **PASS** danh tính môi trường | Ubuntu trên WSL2 x86_64, kernel `6.6.87.2-microsoft-standard-WSL2`. 18 CPU logic, 7,6 GiB RAM, 6,6 GiB khả dụng lúc đo, 2 GiB swap chưa sử dụng. |
| **PASS** dung lượng | Đo ổ Windows tại workspace bằng `df -h .` và `df -B1 --output=avail .`. Lúc đầu khoảng 45 GiB, lần đo sau còn 39.307.010.048 byte (~36,6 GiB), trên ngưỡng 15 GiB. Dữ liệu trong ba worktree đo được 881.341 byte. Phần chênh trên ổ dùng chung chưa xác định nguồn. |
| **BLOCKED** Docker | `docker version` trả client 29.9.3 rồi báo `permission denied while trying to connect to the docker API`. Socket tồn tại, group ghi nhận là `nogroup`, tiến trình thuộc group này và phép `socket.connect()` trực tiếp trả `EPERM`. Quyền truy cập từ host theo thông tin bàn giao và kết quả trong sandbox là hai phép kiểm riêng. |
| **BLOCKED** cổng | `ss -ltn` báo `Cannot open netlink socket: Operation not permitted`. Thử bind `127.0.0.1:0` trả `EPERM`. Chưa xác định được cổng trống từ phiên này. |
| **BLOCKED** HTTPS và tải artifact | Curl trả mã 6 `Could not resolve host` với GitHub, GHCR, get.helm.sh, PyPI, files.pythonhosted.org và registry-1.docker.io. Thử tải checksum Helm v4.3.2 và hai chart pin cũng nhận mã 6. Không có bytes để kiểm checksum. |
| **PASS** công cụ đã có | Terraform 1.17.2, Ansible core 2.22.0, ansible-lint 26.11.1, kubectl 1.36.1 (Kustomize 5.8.1), Python 3.14.4, pip 25.1.1, pipx 1.8.0, gh 2.46.0, Docker CLI 29.9.3. Ansible chạy từ môi trường pipx có sẵn với Jinja 3.1.6 và PyYAML 6.0.4. |
| **BLOCKED** công cụ thiếu | Helm, k3d, Trivy, Gitleaks, actionlint, k6, promtool, Alloy và trình duyệt chạy được trong Linux chưa sẵn sàng. Flask và PuLP thiếu trong Python; cache pip kiểm tra chỉ có các wheel công cụ, không có các wheel này. Không cài artifact mới. |

Tiền kiểm chỉ dùng các endpoint công khai và fixture. Không thực hiện thao tác AWS, kết nối EC2, push, tạo PR, merge, publish hoặc kích hoạt promotion/preview. Không gọi thao tác ghi Docker, không tạo container, ảnh, volume hay cụm. Vì daemon bị chặn, số lượng 12 volume chỉ có từ bàn giao và chưa được đếm lại. Không có số đo CPU/RAM/đĩa của workload hoặc telemetry runtime.

## Ma trận nghiệm thu

| Pha | Phân loại | Bằng chứng và phần còn thiếu |
| --- | --- | --- |
| R2.2 Reproducibility | **BLOCKED** | Dockerfile vẫn dùng `python:3.12-slim` và requirements còn dùng khoảng version. OCI digest, lock hash cho Linux và build/scan chính ảnh đó chưa xác minh được. R1-12 giữ mở. |
| R2.2 Build, runtime và security | **BLOCKED** | 5/5 kiểm tra bảo vệ workflow Workload đạt. Docker build, non-root, health, metrics, graceful shutdown, Trivy, Gitleaks và actionlint chưa chạy. Kiểm tra workflow bằng Python không thay kết quả actionlint hay scanner. |
| R2.3 Ansible tĩnh | **PASS** | Inventory CLI đọc cả ba profile fixture. Profile `private` có một server và hai worker. Hai syntax check đạt. Lint ban đầu **FAIL** với hai lỗi `no-relative-paths`. Sửa đường dẫn tương đối theo `playbook_dir`, thêm regression, chạy lại đạt 8/8 unit tests và lint 0 lỗi trên 5 file. |
| R2.3 Ansible runtime | **BLOCKED** | Ping chỉ dùng localhost và local transport nhưng Ansible báo `Local RPC server did not start`. Baseline hệ điều hành, cài K3s, join và idempotency chưa chạy. Fixture SSM chỉ dùng cho parser và syntax check. |
| R2.4 Kubernetes | **BLOCKED** | Docker, k3d, Helm và local ports chưa sẵn sàng. Chưa có cụm ba node, node readiness, deploy, service, ingress/TLS, probes, requests/limits, NetworkPolicy, PDB, HPA hay lịch đặt Pod được quan sát. R1-08 còn mở. |
| R2.5 GitOps | **BLOCKED** | Chưa triển khai Argo CD hay nguồn Git local. Chưa có sync, drift correction, thay đổi có kiểm soát hoặc rollback qua controller. |
| R2.6 Observability | **BLOCKED** | Ba ca Config về cấu hình metrics/alerts, log RBAC và Loki storage/policy đạt. Ca render ServiceMonitor/NetworkPolicy dừng vì thiếu `helm`. Tải kube-prometheus-stack 85.0.0 và Loki 18.7.6 thất bại. Alloy v1.22.0 là pin của Config, chưa xác minh artifact/runtime. Chưa có scrape, ingestion, dashboard, đánh giá alert, gửi alert hay số đo footprint. |
| R2.7 Portal và optimizer | **BLOCKED** | Không bind được loopback. Thiếu Flask, trình duyệt Linux và PuLP. Test snapshot thử chạy nhưng import PuLP thất bại. Chưa có browser OIDC, RBAC, catalog, request, preview, audit, rollback hay GitOps thật. Chưa thu được Node/Pod metrics, kết quả ILP trên node thật hoặc bằng chứng workload placement. Các chi phí và nhãn vùng trong dữ liệu lịch sử là mô phỏng. |
| R2.8 E2E | **BLOCKED** | Chưa có build → scan → deploy → availability → monitoring, dữ liệu k6, HPA scale, hỏng Pod, drain và rescheduling hoặc rollback. |
| Hosted và AWS | **NOT RUN** | Ngoài phạm vi R2. Các gate tiếp tục đóng. |

## Tái lập và dọn dẹp

Chạy từ workspace để tái lập các phép kiểm môi trường. Trước khi tạo tài nguyên Docker trong bất kỳ lần chạy R2 tiếp theo, ghi lại tên của các volume hiện hữu và dung lượng ổ Windows. Dừng tác vụ nặng trước ngưỡng 15 GiB.

```sh
df -h .
df -B1 --output=avail .
free -h
nproc
docker version
ss -ltn
curl --disable -fsSL --max-time 5 -o /dev/null https://get.helm.sh/helm-v4.3.2-linux-amd64.tar.gz.sha256
```

Tái lập syntax, lint và inventory từ worktree Platform. Các lệnh dưới chỉ phân tích fixture, không chạy task trên inventory.

```sh
t=$(mktemp -d /tmp/idp-r2-ansible.XXXXXXXX)
export ANSIBLE_HOME="$t/ansible" ANSIBLE_LOCAL_TEMP="$t/tmp"
mkdir -p "$ANSIBLE_HOME" "$ANSIBLE_LOCAL_TEMP"
python3 -B infra/ansible/render_inventory.py \
  --terraform-output infra/terraform/modules/ansible-inventory/tests/fixtures/private.json \
  --environment lab --region us-east-1 --transfer-bucket example-lab-transfer \
  --output "$t/private.json"
ansible-inventory -i "$t/private.json" --graph
ansible-playbook -i "$t/private.json" infra/ansible/playbooks/linux-baseline.yml --syntax-check
ansible-playbook -i "$t/private.json" infra/ansible/playbooks/bootstrap-lab.yml --syntax-check
ansible-lint --offline --project-dir "$PWD" \
  infra/ansible/playbooks/linux-baseline.yml infra/ansible/playbooks/bootstrap-lab.yml
python3 -B -m unittest discover -s tests -p 'test_ansible*.py' -v
```

Ca Python cần PyYAML và Jinja2. Phiên này lấy chúng từ môi trường Ansible pipx sẵn có qua `PYTHONPATH`. Chi tiết các bộ kiểm khác ở [kết quả kiểm thử](TEST_RESULTS.md#kết-quả-bổ-sung-r2). Lệnh mô phỏng và smoke loopback cũ nằm trong [kế hoạch kiểm thử](TEST_PLAN.md).

Khi môi trường thực thi có Docker và cổng local, dùng một tên mới dành riêng cho R2, một kubeconfig tạm riêng và context `k3d-<tên-cụm>`. Cần đối chiếu tên cụm và danh sách volume trước/sau bằng các lệnh sau. Chỉ xóa cụm do chính lần thử tạo và đã đối chiếu tên. Các lệnh dưới **NOT RUN** trong phiên này.

```sh
docker volume ls --format '{{.Name}}' | sort
k3d cluster list
# Dùng tên chính xác của cụm R2 đã xác minh.
k3d cluster delete "$R2_CLUSTER"
docker volume ls --format '{{.Name}}' | sort
```

Không có tài nguyên Docker cần dọn trong phiên này. Các worktree, refs và commit R2 được giữ để tiếp tục từ đúng SHA. Dữ liệu tạm của Ansible được giữ trong thư mục `/tmp/idp-r2-ansible.*` riêng của phiên. Xóa từng thư mục thử bằng đường dẫn cụ thể sau khi lấy xong bằng chứng. Tránh dùng wildcard để dọn tài nguyên.

## Điều kiện đánh giá lại R3

Cần bằng chứng từ cùng môi trường thực thi cho Docker, download và loopback, rồi xác minh R1-12 bằng digest/lock đã kiểm chứng và build/scan Linux. Sau đó cần chạy Ansible trên Linux cô lập không dùng AWS, nghiệm thu cluster ba node, quan sát Argo CD và telemetry, kiểm browser/optimizer dựa trên snapshot thực và ghi kết quả k6, HPA, drill hỏng Pod/drain và rollback. Chỉ đánh giá lại R3 sau khi các kiểm tra bắt buộc có kết quả thực tế. [Sổ lỗi](DEFECT_REGISTER.md)
