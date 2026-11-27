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
