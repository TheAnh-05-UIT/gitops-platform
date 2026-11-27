# R2 — Nghiệm thu runtime cục bộ

## Kết quả sau khi khôi phục quyền ngày 2026-11-27

**R2 chưa đạt điều kiện chuyển sang R3.** Build và thử nghiệm tích hợp cục bộ đã chạy. Trivy trả exit 1 vì các lỗ hổng HIGH trong hệ điều hành của ảnh Workload được pin. Đợt Ansible đầy đủ dừng ở ngưỡng đĩa dự phòng, trước khi kiểm được idempotency của toàn bộ topology. Các kết quả bên dưới áp dụng cho lab cục bộ và các SHA ghi trong báo cáo.

| Hạng mục | Kết quả và bằng chứng |
| --- | --- |
| R2.0 Môi trường | **PASS.** Docker client/Engine 29.9.3, 12 volume nền, bind Python trên loopback, tải Helm 17.344.287 byte và ghi thử cả ba worktree. DNS/TLS đạt với GitHub, GHCR, PyPI và Docker Hub. GHCR và Docker Registry trả HTTP 401 cho truy cập ẩn danh. PowerShell truy vấn Windows sau khi được cấp quyền ngoài sandbox. Ổ C chứa workspace và VHDX Docker, có 36,52 GiB khi tiền kiểm. Ổ D có 5,01 GiB và nằm ngoài nơi lưu R2. |
| R2.1 Công cụ | **PASS.** Các binary đã kiểm nằm trong `.r2-runtime-tools/bin` ở workspace cha. Helm 4.3.2, k3d 5.8.3, Trivy 0.76.2, Gitleaks 8.30.1, actionlint 1.7.12, k6 2.4.0, promtool 3.16.0 và Alloy 1.22.0 được đối chiếu SHA256 với checksum hoặc release metadata. Playwright 1.65.2 và Chromium Headless Shell 159.0.8154.6 chạy với browser sandbox bật và thư viện Ubuntu giải nén cục bộ. |
| R1-12 Reproducibility | **PASS phạm vi linux/amd64.** Workload `b0ddbba334fd1422540a0369215f0ed225770548` pin OCI index `sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b` và Linux manifest đã pull `sha256:4a68d3169325c47e1bafbb86425220f03fbdff6f079a419e8d39407183288217`. Chín dependency được giải trên CPython 3.12 Linux, hash khớp PyPI và Docker build thành công với `--require-hashes --only-binary=:all:`. Các kiến trúc khác chưa build. |
| R2.2 Ảnh Linux và scan | **PASS build/runtime. FAIL vulnerability gate.** Docker image ID `sha256:dfbce3b3b8c3abc7962980c747eb3ec09d9d1be9e07dd17968b9a67b111669dd`, UID/GID 10001, health/identity/RED metrics đạt, SIGTERM exit 0. Trivy quét đúng local tag, 54 HIGH, 0 CRITICAL và 0 secret. Một mục có bản sửa trong dữ liệu Trivy (`libzstd1`), 53 mục không có phiên bản vá ghi nhận. Ảnh Bookworm đối chứng có 100 HIGH và 2 CRITICAL. SBOM CycloneDX 1.7 có 98 thành phần. |
| R2.3 Ansible | **PASS** local connection và chuẩn bị node Linux cô lập. `k3s-node.yml` chạy trên Ubuntu 24.04 với Docker transport, xác minh checksum binary K3s, tạo ownership marker và render systemd unit. Hai lượt có `changed=4` và `changed=0`, đều `failed=0`. **BLOCKED** cho bootstrap đầy đủ hai lượt. Lab dùng bản sao playbook thay duy nhất assertion transport sang Docker, cài `iproute2` để thu facts và dùng K3s drop-in `snapshotter: native` sau khi nested overlayfs bị từ chối. Systemd server và worker đầu đều Ready với K3s v1.36.1+k3s1. Worker thứ hai đã nhận token TLS-pinned và bắt đầu handler khởi động khi guard dừng lab. Kiểm tra toàn topology và lượt thứ hai chưa chạy xong. |
| R2.4 Kubernetes | **PASS.** k3d `idp-r2-accept` có một server, hai worker, cả ba Ready với k3s v1.36.1+k3s1. Hai workload replicas chạy trên hai worker có nhãn vùng mô phỏng. Helm lint, render và deployment policy đạt. Ingress TLS trả JSON qua chứng chỉ lab đã tin cậy, `/metrics` trên ingress trả 404 theo route exact `/`, health nội bộ trả 200. Probes, requests/limits, PDB và HPA từ chart được triển khai thực. |
| R2.5 Argo CD | **PASS.** Argo CD 3.6.3 dùng Git Smart HTTP chỉ đọc trong cụm. Baseline `4c40b5cfe1a674568e3970a892e104d12b89a575` Synced/Healthy, drift replicas 2→1 được self-heal về 2. Revision thử HPA `725d036ad06123f6f71a8d61051d9de8e79043f1` Synced/Healthy. Revert `bb0c5559c93acb4c8be395e7bdb642e8b764cf59` xóa HPA, trả về hai replicas và cùng Git tree với baseline. |
| R2.6 Observability | **PASS thu thập, truy vấn và alert thực.** kube-prometheus-stack 85.0.0 và Loki 18.7.6 khớp SHA256 của upstream release, hai workload targets UP, RED request counter quan sát được, Grafana dashboard `workload-api-red` có ba panel. Alloy gửi 20 mẫu sự kiện đã lọc sang Loki, Grafana truy vấn được datasource Loki. Alertmanager nhận alert kiểm thử do Prometheus gửi. Sửa route Alertmanager kế thừa receiver `null` bị thiếu và xử lý ký tự xuống dòng trong log CRI. Release Loki cài cục bộ dùng tên `workload-logs` nên selector mặc định `lab-loki` ban đầu không chọn Pod. Render với release name trong runbook có selector khớp. Sau khi sửa selector riêng trong lab, Grafana proxy tới Loki `/ready` thành công và Pod ngoài namespace bị từ chối kết nối. Cả hai ca chạy sau khi khởi động lại k3d. Footprint tại một mẫu metrics là 68 mCPU và 866 MiB cho mười Pod observability. |
| R2.7 Portal và optimizer | **PASS trong lab.** Chromium qua TLS thử login với OIDC provider giả lập cục bộ, PKCE, nonce, cookie Secure/HttpOnly, replay 400 và viewer POST 403. Deployer preview động đề xuất ba replicas dựa trên snapshot Kubernetes thật, xác nhận diff và submit 403 khi cổng ghi đóng. Adapter GitHub chỉ đọc dữ liệu từ Git local qua test double. Node/Pod và metrics lấy từ kube API. PuLP/CBC Optimal 5/5, median 5,35 ms. Ước lượng latency dùng 7 mẫu thời gian đến byte đầu từ ingress lab, median 11,43 ms, không có input giá. |
| R2.8 Load và recovery | **PASS.** k6 chuẩn 3 VU/30 giây, 90/90 requests hợp lệ, p95 18,93 ms. Kịch bản HPA lab 100 req/s trong 75 giây, 7.501/7.501 hợp lệ, p95 5,65 ms, mục tiêu CPU riêng của bài thử 10%, scale 2→3. Xóa một Pod và quan sát Pod thay thế Ready. Drain giới hạn selector Workload qua eviction/PDB, hai replicas Ready trên worker còn lại, sau đó uncordon. Git revert được controller đồng bộ về baseline. |
| Hosted và AWS | **NOT RUN** ngoài phạm vi. Portal dùng IdP giả lập và adapter GitHub local. History adapter ràng buộc repo HTTPS GitHub và AppProject chuẩn, nên đường history Portal nối Argo thật chưa chạy trong lab Smart HTTP. |

Config commits `dfd3486a92e69afe62d63884190199a122381f6a` và `b235d282e2b500beb3450ffaf6a696f6c1e57204` sửa hai lỗi quan sát được. Platform giữ commit Ansible `8b7886e15c65c3887d1c658bb0922d5c4c8d7bae`. Chi tiết kiểm thử và lỗi còn mở nằm trong [TEST_RESULTS](TEST_RESULTS.md) và [DEFECT_REGISTER](DEFECT_REGISTER.md).

### Ngưỡng đĩa và trạng thái bàn giao

`df -B1 --output=avail /mnt/c` được lấy mẫu khi chạy load và bootstrap. Ngưỡng dừng sớm là 17 GiB để giữ mức tối thiểu 15 GiB. Ansible dừng khi mẫu còn 18.042.568.704 byte, khoảng 16,80 GiB. Sau dừng, C còn 17.438.568.448 byte, khoảng 16,24 GiB. Các container Ansible của lần chạy đã dừng. k3d `idp-r2-accept` đã dừng và được giữ để tái lập. So sánh danh sách trước và sau xác nhận đủ 12 volume gốc.

Để đánh giá lại R3, cần chạy lại full bootstrap và lượt idempotency với đĩa đủ dư và xử lý gate ảnh Workload bằng bản vá hoặc base đã được quét đạt. Portal history dùng hợp đồng Argo/GitHub chuẩn và chưa có bằng chứng tích hợp thật trong lần chạy này.

## Checkpoint ban đầu

**Checkpoint trước khi khôi phục quyền ngày 2026-11-27 — BLOCKED. Chưa đủ bằng chứng để chuyển sang R3 Hosted Integration.** Kiểm tra Ansible syntax, inventory và lint đã đạt sau một bản sửa cục bộ. Tiến trình Codex bị từ chối khi kết nối Docker và mở cổng loopback, đồng thời không phân giải được các máy chủ chứa artifact. Chuỗi build → scan → GitOps → phục vụ → giám sát → phục hồi → rollback vẫn chưa được nghiệm thu. R1-12 còn mở.

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

### Điều kiện đánh giá lại R3 tại checkpoint ban đầu

Cần bằng chứng từ cùng môi trường thực thi cho Docker, download và loopback, rồi xác minh R1-12 bằng digest/lock đã kiểm chứng và build/scan Linux. Sau đó cần chạy Ansible trên Linux cô lập không dùng AWS, nghiệm thu cluster ba node, quan sát Argo CD và telemetry, kiểm browser/optimizer dựa trên snapshot thực và ghi kết quả k6, HPA, drill hỏng Pod/drain và rollback. Chỉ đánh giá lại R3 sau khi các kiểm tra bắt buộc có kết quả thực tế. [Sổ lỗi](DEFECT_REGISTER.md)
