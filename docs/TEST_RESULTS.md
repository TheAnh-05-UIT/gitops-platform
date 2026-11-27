# Kết quả kiểm chứng P0–P7

Mốc review trước sửa là Platform `9a807b6`, Config `59a61aa`, Workload `626f62b`. R1 dùng bản xuất tách biệt và kiểm đủ 111 Terraform mock, Python bootstrap 7/7, Platform 52/52, Config 55/55 và Workload 15/15. Mười bốn ca bootstrap Terraform nằm trong 111, còn bảy ca Python nằm riêng. Vòng nghiệm thu chạy lại ba bộ Python trên cùng bản xuất và xác nhận 52/55/15. Các ca fail chủ đích và ca bổ sung có danh mục trong [sổ lỗi](DEFECT_REGISTER.md).

## Kiểm tra sau sửa

| Nhóm | Lệnh và phạm vi | Kết quả |
| --- | --- | --- |
| Terraform | `terraform -chdir=infra/terraform fmt -check -recursive`, `python -B scripts/terraform_offline.py --provider-mirror <local-mirror>` | PASS 113/113. Lab 51, bootstrap 14, inventory 9, compute 11, IAM 8, networking 8, security 12. Bảy validate đạt. Backend disabled, provider mirror/lock cục bộ, mock only. |
| Python | `python -B -m unittest discover -s tests -v` từ ba worktree và biến checkout cho hai repo sibling | PASS. Số ca cuối được xác nhận ở bảng SHA trong [nghiệm thu](FINAL_ACCEPTANCE.md). |
| Bootstrap | `python -B -m unittest discover -s infra/terraform/bootstrap/tests -v` | PASS 7/7. Tách khỏi hai số Terraform và Python toàn repo. |
| Helm | `helm lint` chart mặc định, private, overlay metrics và demo; `helm template` và `scripts/check_deployment_policies.py` | PASS 4 lint và policy. Config suite chạy thêm render exact tree, HPA/NetworkPolicy/quota, negatives và Argo demo scope. |
| HTTP local | Werkzeug WSGI bind cổng động ở `127.0.0.1`, GET `/`, `/healthz`, `/metrics` | PASS HTTP 200. Đây là tiến trình Flask thật, không qua Gunicorn hoặc container. |
| Portal HTTPS | `python -B -m scripts.verify_portal_loopback`; hai listener loopback và test CA | PASS chuỗi anonymous 401, login/callback 302, catalog 200, viewer mutation 403, replay 400. Code/verifier được kiểm qua đường TLS. Portal PR và Argo ở các ca khác dùng doubles. |
| Browser local | Chrome và Edge `--headless --disable-gpu --dump-dom` với profile tạm và một data URL kiểm tra. Playwright thử tới listener loopback cô lập. | BLOCKED. Cả hai browser báo GPU process không dùng được, exit 2147483651, không có DOM. Playwright trả `ERR_CONNECTION_REFUSED`. Portal qua browser NOT RUN. |
| Security tĩnh | `python -B -m pip check`, parse Python AST/JSON/YAML, `bash --noprofile --norc -n` cho 18 workflow steps, pattern scan trên ba cây source | PASS, không thấy credential pattern. Kiểm tra pattern không thay scanner. |
| Load syntax | `Get-Content tests/load/workload-api.js -Raw \| node --input-type=module --check` | PASS cú pháp. Không phát tải k6. |
| Container | Docker CLI với `--config` cô lập và `--host npipe:////./pipe/docker_engine` | BLOCKED. Named pipe không có và Docker không kết nối daemon. Build, container startup/non-root/graceful shutdown và scan image NOT RUN. |
| Host | `wsl --list --verbose`; `Get-Command docker,wsl,python,terraform,ansible-playbook,ansible-lint,kubectl,helm,k3d,trivy,gitleaks,actionlint,k6` | WSL BLOCKED `E_ACCESSDENIED`. Thiếu Ansible CLI/lint, k3d, Trivy, Gitleaks, actionlint, k6 trên PATH. Không cài system-wide. |
| Ansible/K3s | Inventory fixtures, template/runbook static checks | PASS offline. Syntax của Ansible CLI, local Linux install/join/idempotency và Argo bootstrap NOT RUN. |
| Upstream observability | `curl.exe --disable --fail --location` của đúng hai release chart Prometheus 85.0.0 và Loki 18.7.6, giới hạn thời gian | BLOCKED do exit 7 kết nối `github.com:443`. Chart Workload đã lint với bộ values tích hợp metrics. Không có downstream render/operator, PromQL/Alloy validation, alert, log ingestion và overhead thực. |
| E2E runtime | Local K3s 3 node, Argo reconcile/drift, tải k6, HPA, drain, TLS CNI, Pod failure/rollback/restore | BLOCKED bởi docker/k3d và toolchain. Vòng mô phỏng hiện chỉ chứng minh health, snapshot/placement, PR payload, Helm và SQLite fixture. |
| AWS/GitHub | AWS API, state remote, GHCR dự án, hosted CI, push/PR, publish, rollout | NOT RUN theo chính sách owner. |

Môi trường dùng Python 3.14.3, Flask 3.1.3, Requests 2.34.2, PuLP 3.3.0, Jinja2 3.1.6 và PyYAML cache. Terraform 1.15.5 với AWS provider 6.73.0, Helm 4.3.2 và kubectl client 1.36.1. Python 3.12 runner và container Linux chưa xác minh.

## Benchmark

Chạy CLI từ Platform, lặp 7 lần mỗi case. Báo thời gian median cục bộ bằng mili giây, có overhead chạy CBC process.

| Case | CBC | Greedy | Exhaustive |
| --- | --- | --- | --- |
| Baseline CSV | 0,026667 mô phỏng · 86,781 ms | 0,028800 · 0,011 ms | 0,026667 · 0,015 ms |
| Snapshot hai worker | 0,724 · 73,746 ms | 0,738 · 0,019 ms | 0,724 · 0,039 ms |
| Infeasible | Infeasible · 0,001 ms | NoSolutionFound · 0,003 ms | Infeasible · 0,001 ms |

Greedy lệch 8% ở baseline và 1,934% ở snapshot, theo mục tiêu từng mô hình. Các ca CPU/memory không đủ, vùng không tương thích, stale metrics và multi-workload được kiểm bằng fixture, không có phép đo tiết kiệm AWS. [Kế hoạch và lệnh](TEST_PLAN.md)

## Kết quả bổ sung R2

Bảng này ghi phép đo mới trong WSL2. Các số P0–P7 ở trên là hồ sơ lịch sử và không được cộng vào kết quả R2.

| Cách chạy | Kết quả trong R2 |
| --- | --- |
| `python3 -B -m unittest discover -s tests -p 'test_ansible*.py' -v` tại Platform | **PASS** 8/8, gồm regression phân giải đường dẫn của cả hai template. Môi trường Python dùng PyYAML/Jinja2 có sẵn từ Ansible pipx. |
| `render_inventory.py` và `ansible-inventory -i <fixture-output> --graph` | **PASS** cả ba profile, lần lượt 0, 1, 2 agents. |
| `ansible-playbook -i <private-fixture> <playbook> --syntax-check` | **PASS** linux-baseline và bootstrap-lab. |
| `ansible-lint --offline --project-dir "$PWD" infra/ansible/playbooks/{linux-baseline,bootstrap-lab}.yml` | **FAIL** ban đầu (exit 2, hai `no-relative-paths`). **PASS** sau sửa (exit 0, 5 file, profile production). |
| `ansible localhost -i localhost, -c local -m ansible.builtin.ping` | **BLOCKED**, lỗi khởi động local RPC. |
| `python3 -B -m unittest discover -s tests -p test_k3s_restore_rehearsal.py` tại Platform | **PASS** 7/7 fixture. Chưa restore trên cụm. |
| `python3 -B -m unittest discover -s tests -p test_cross_repo_release.py` tại Platform | **PASS** hai ca, một ca skip. Biến `PLATFORM_CONFIG_CHECKOUT` và `PLATFORM_WORKLOAD_CHECKOUT` trỏ worktree R2. |
| `python3 -B -m unittest discover -s tests -p test_workflow_security.py` tại Workload | **PASS** 5/5. |
| `python3 -B -m unittest discover -s tests -p test_observability.py` tại Config | **PASS** 3 ca tĩnh. Một ca **BLOCKED** bởi `FileNotFoundError: helm`, khiến lệnh đầy đủ trả exit 1. Ba ca tĩnh chạy lại riêng đều exit 0. |
| `python3 -B -m unittest discover -s tests -p test_snapshot_capture.py -v` tại Platform | **BLOCKED** tại import `pulp`, chưa thực thi ca snapshot. |
| `terraform -chdir=infra/terraform fmt -check -recursive` tại Platform | **PASS** exit 0. Provider init, plan và các thao tác AWS **NOT RUN**. |

Các phép kiểm build, scan, cluster, Argo CD, portal/ILP, observability và E2E còn lại được phân loại theo từng pha trong [nghiệm thu R2](LOCAL_RUNTIME_ACCEPTANCE.md).

## R2 sau khôi phục môi trường thực thi

| Phép kiểm | Kết quả quan sát |
| --- | --- |
| Workload unittest, actionlint và Gitleaks thư mục Workload | **PASS** 16/16, workflow lint exit 0, Gitleaks scan thư mục báo 0 leaks. |
| Docker build, `pip check`, HTTP smoke và SIGTERM | **PASS.** 6/6 regression runtime trong chính ảnh. Hash-locked linux/amd64 build, 9 gói Python, không có broken requirements, UID/GID 10001, health/identity/metrics, exit 0 sau SIGTERM. |
| Trivy image vulnerability/secret và CycloneDX | **FAIL** vulnerability policy trên cả trixie và Bookworm. Trixie 54 HIGH, Bookworm 100 HIGH và 2 CRITICAL. Trixie không báo secret. SBOM có 98 thành phần. |
| Ansible local transport và Ubuntu 24.04 qua Docker transport | **PASS** pong. Hai lượt chạy node preparation `changed=4`, `changed=0`, `failed=0`. **BLOCKED** full systemd bootstrap tại disk guard. Server và worker đầu Ready, worker thứ hai đang start. Lượt bootstrap idempotency đầy đủ chưa chạy. |
| Config observability tests, Helm lint, policy script và validators | **PASS** 4/4, chart lint/render và deployment policy exit 0, Alloy validate và promtool kiểm 2 rule đạt. |
| Argo CD và Kubernetes | **PASS** 3 Ready nodes, sync và health đúng Git SHA, drift 1→2, Pod thay thế Ready, drain một worker hạn chế theo selector, hai replicas Ready sau reschedule, Git revert phục hồi baseline. |
| Prometheus, Loki, Alloy, Grafana và Alertmanager | **PASS** 2/2 targets UP, RED counter 2.965 tại lần query, 20 log events lọc đúng, ba dashboard panels, Grafana truy vấn Loki và Alertmanager nhận alert tổng hợp. Sau khi chỉnh selector lab, Grafana proxy tới Loki `/ready` thành công và kết nối từ namespace ngoài bị từ chối. |
| Snapshot capture và Portal | **PASS** 3/3 snapshot tests. Export live và 5/5 lượt ILP Optimal, browser OIDC/RBAC và preview dựa trên observed data, submit đóng trả 403. |
| k6 | **PASS** 90/90 ở 3 VU/30s p95 18,93 ms. 7.501/7.501 ở 100 req/s–75s p95 5,65 ms. HPA từ 2 lên 3 tại CPU 56% so với target lab 10%. |

Xem [ma trận R2](LOCAL_RUNTIME_ACCEPTANCE.md) để đối chiếu phạm vi của từng ca và SHA.

### R2 kiểm lại ảnh Alpine

Ảnh từ Workload `1fa207e` xây trên linux/amd64 với OCI digest và musllinux wheel hash. **PASS** Trivy 0 HIGH, 0 CRITICAL, 0 secret, CycloneDX có 49 thành phần. `pip check`, 6/6 runtime tests, HTTP health/identity/metrics và SIGTERM đều đạt. Ảnh Alpine chưa vá trước đó có 16 HIGH của `krb5-libs`.

Argo CD đồng bộ revision lab `f392cf2` và triển khai hai Pod Ready của đúng ảnh đã quét. Health và identity qua Service trả HTTP 200.

### R2 kiểm lại Ansible trên systemd

Docker transport với Ubuntu 24.04.5, K3s v1.36.1+k3s1, native snapshotter và tmpfs riêng. **PASS** full playbook với 11/9/9 thay đổi trên server/worker/worker. Ba node Ready, cả hai worker có nhãn vùng mô phỏng. Chạy lại cùng inventory cho 0 thay đổi, 0 lỗi trên cả ba host. Xem điều kiện của lab trong [nghiệm thu R2](LOCAL_RUNTIME_ACCEPTANCE.md#ansible-full-bootstrap-và-idempotency-kiểm-lại).
