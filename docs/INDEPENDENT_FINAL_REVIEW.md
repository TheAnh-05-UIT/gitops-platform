# R1 — Rà soát kỹ thuật độc lập P0–P7

Phạm vi đánh giá R1 là ba SHA gốc. Kết quả sửa lỗi và tái kiểm thử nằm trong [sổ lỗi](DEFECT_REGISTER.md) và [báo cáo nghiệm thu](FINAL_ACCEPTANCE.md).

## Kết luận điều hành

**NOT READY cho tích hợp offline đầy đủ, kiểm chứng runtime toàn hệ thống và kích hoạt hosted.** Đã tái lập đủ các số kiểm thử được báo cáo. Ba ca ngoài suite xác nhận lỗi giao tiếp giữa những thành phần riêng lẻ đang pass. Guard promotion từ chối chart hợp lệ khi bật NetworkPolicy hoặc HPA, portal ký preview dựa trên nhu cầu CPU khác Git, và Terraform chấp nhận nhãn mà bộ chuyển inventory Ansible từ chối. Workload HTTP chạy được qua WSGI cục bộ. Chưa có bằng chứng chạy container hoặc toàn bộ lab.

Các checkpoint có triển khai thực chất. Terraform và Ansible có các module, role, playbook, ranh giới quyền và quy trình recovery cụ thể. Config có manifest GitOps và các tùy chọn Kubernetes. Workload phát telemetry và chạy được hai entry point demo qua kiểm thử. Optimizer có mô hình đa workload và kết quả tái lập. Phần tự động tạo PR promotion ảnh vẫn thiếu, và các kết nối hosted hoặc runtime không thể suy ra từ mock.

Không sửa mã nguồn, ứng viên, policy, index hoặc lịch sử Git. Không chạy AWS, gọi GitHub API của dự án, triển khai vào Kubernetes, kích hoạt workflow, phát hành ảnh, khởi động lại Docker Desktop hay WSL. Báo cáo này là tệp duy nhất tạo trong checkout làm việc. Dùng tài liệu chuẩn công khai để đối chiếu các hợp đồng bên ngoài.

## Checkpoint và phương pháp

| Repo | Commit đã xác minh | Worktree giữ nguyên |
| --- | --- | --- |
| Platform | `9a807b6bda9e8a3f25bb26dc16ca6d2acb105201` | `feat/provision-aws-k3s-infrastructure` |
| Config | `59a61aa167c85b4fb29d1f6687bb9f8e485d0f07` | `feat/offline-config-lab` |
| Workload | `626f62bdf1c3b80ddeb146e15ebf32ba6831977f` | `feat/offline-workload-lab` |

Đối chiếu `git rev-parse '<SHA>^{commit}'`, `git worktree list --porcelain` và `git status --short`. Xuất từng SHA bằng `git archive` vào thư mục riêng và chạy kiểm thử trên bản xuất. Config và Workload gốc vẫn ở `9564111` và `e21e077`. Các ref remote-tracking chỉ phản ánh dữ liệu cache. Platform lệch cached `origin/main` theo chiều 9 commit riêng và 3 commit riêng phía main. Khi được phép tích hợp hosted, cần xác minh lại base và cây merge.

Đã đọc AGENTS ở parent và các repo, workspace policy và các skill dự án liên quan. Đã đối chiếu FINAL_REVIEW, ARCHITECTURE, ROADMAP, PROJECT_STATE, EXECUTION_LOG, QUALITY_GATES, MANUAL_AWS_GATES, SECURITY, ADR và runbook. ADR 0003/0004 và AWS_LAB_DESIGN tồn tại ở checkout gốc dưới dạng untracked. Chúng cung cấp ngữ cảnh thiết kế, nhưng không có trong SHA Platform. Nguồn, line number và kết quả dưới đây áp dụng cho các SHA trong bảng.

## Kiến trúc và ma trận xác minh

Chuỗi dự kiến gồm Terraform → inventory v1 → Ansible/SSM → K3s → Argo CD đồng bộ bản Git đã duyệt. Workload CI build, smoke, scan và ghi receipt cho artefact được phát hành. Config giữ giá trị mong muốn và kiểm tra candidate. Portal đề xuất PR placement, đọc trạng thái Argo và dùng snapshot làm đầu vào optimizer. Kubernetes sở hữu quyết định gán Pod. Telemetry hiện là nguồn quan sát riêng, người vận hành phải đưa dữ liệu vào snapshot theo hợp đồng.

| Mốc | Có trong SHA và đã kiểm chứng | Phần còn thiếu hoặc bị chặn |
| --- | --- | --- |
| P0 CI/CD | Build/smoke, handoff theo ID và checksum, Trivy, receipt gắn attempt, guard với reviewer độc lập và rollback theo lịch sử. Hai hard stop Workload và freeze Config có trong mã. | Writer cho PR promotion ảnh; tương thích guard với tùy chọn chart; private registry read và required check chưa được xác minh hosted. |
| P1 Terraform / Ansible | Lab A/B/C, bootstrap S3 riêng, stable keys, inventory v1, Linux baseline, cài K3s từ binary có SHA, token agent, kiểm tra Ready và gắn label. 111 ca mock và render template đã qua. | Sai khác giới hạn nhãn, phiên bản controller, AMI, SSM/S3, K3s install/rejoin/idempotency và AWS-11–16. |
| P2 Kubernetes / GitOps | Service ClusterIP 80 → cổng tên `http` trên 8080, probes `/healthz`, Pod Security Restricted, non-root, seccomp, NetworkPolicy, HPA/PDB và TLS opt-in. Argo AppProject hẹp và sync thủ công. | Chart hợp lệ vẫn bị một số guard từ chối. Traefik/TLS, metrics API, CNI enforce, rollout/drain và phần đồng bộ thực còn pending. |
| P3 Observability | RED theo route/status đã giới hạn, log có allowlist, ServiceMonitor, PrometheusRule, Grafana dashboard, cấu hình kube-prometheus-stack/Loki/Alloy và k6 loopback. | Chưa render gói Helm upstream cục bộ, chạy parser rule/Alloy, đo SLI/SLO hoặc chứng minh ngân sách tài nguyên và lưu giữ. |
| P4 Optimizer | Mô hình CPU, memory, slot, RTT, cost ước tính, áp lực và thay đổi placement. CBC/greedy/exhaustive dùng chung scorer. Snapshot v1 có kiểm tra tuổi dữ liệu. | Thiếu đường thu thập/chuẩn hóa metrics và topology vật lý có thể tái lập. Cần hòa giải với scheduler, quota, rollout và ràng buộc ngoài mô hình. |
| P5 Portal | Auth Code + PKCE, nonce/state, ACL, CSRF, preview ký, PR scoped, kiểm tra provenance branch, đọc history và Argo, placement rollback, journal. Đã kiểm đường từ chối anonymous và proposal của actor khác. | Git requests và snapshot không ràng buộc cùng revision, journal có cửa sổ kết quả mơ hồ, IdP/GitHub App/Argo thực và retention còn pending. |
| P6 Bảo mật và recovery | Policy nguồn/SG và Pod, action pin theo SHA, freeze, runbook SQLite K3s, backend restore và diễn tập SQLite giả lập. | Cần scanner chuyên dụng, ảnh/dependency lock, diễn tập phục hồi thật và bằng chứng RPO/RTO. |
| P7 Demo | API, worker probe và CronJob cùng image hợp đồng. Chart demo opt-in và Argo AppProject/Application mẫu manual. Demo và gate cleanup đã có tài liệu. | Chưa có digest ứng viên được xác minh cùng runtime. Trình tự hé mở các phụ thuộc chưa khép kín giữa promotion, chart, và placement. Chỉ có thể trình diễn fixture đã ghi rõ phạm vi. |

### Kiểm tra hạ tầng theo profile

| Profile | Số node | Mạng và rà soát chi phí |
| --- | --- | --- |
| A | 1 server, 0 worker | Một subnet public, IGW, một IPv4 public trên instance, không NAT/EIP NAT. SSM và egress web, không mở inbound quản trị. |
| B khởi đầu / demo | 1 server + 1 / 2 worker | Một subnet public, IGW, IPv4 per-instance. Các node liên lạc qua IP private. `worker_count=2` giữ ID `k3s-server` và `k3s-agent1`, thêm `k3s-agent2`. |
| C | 1 server + 1 hoặc 2 worker | Subnet public/private cùng AZ và route NAT cho node private. Một NAT và EIP khi opt-in bắt buộc. Node không có IPv4 public. |

SG dùng tham chiếu vai trò cho TCP 6443, UDP 8472 và TCP 10250 theo topology. Tuỳ chọn ingress A/B cần CIDR và role. EC2 yêu cầu IMDSv2 hop 1, gp3 mã hóa và instance profile EC2 chứa `AmazonSSMManagedInstanceCore`. Bootstrap S3 có versioning, SSE-S3, TLS deny, public access block, BucketOwnerEnforced và chống hủy mặc định. Lab dùng state key theo môi trường và S3 `.tflock`. Lab role có quyền state/lock tách biệt và quyền xóa chỉ cho lock. Recovery role và backup tách riêng. Các kiểm tra xác nhận graph và tài liệu phân quyền. IAM hiệu lực, đăng ký SSM, S3 locking, AMI, dwell time, routing và khôi phục thật vẫn cần bằng chứng owner.

Chi phí được mô tả theo EC2, EBS, IPv4, NAT, egress, S3 storage/versions/requests và overhead telemetry. Một server và một AZ tạo cùng miền lỗi. Kho state hoặc đĩa giữ lại có vòng đời riêng. RPO 24 giờ và RTO 60 phút là mục tiêu lab cho kịch bản same-server, chưa có đo lường. [Terraform](../infra/terraform/README.md) · [State runbook](TERRAFORM_STATE_RUNBOOK.md) · [Recovery](RECOVERY_RUNBOOK.md)

## Phát hiện có ảnh hưởng lớn

### R1-01 — HIGH · Config · Guard promotion và cấu hình Helm hợp lệ xung đột

- **Vị trí.** `scripts/check_promotion.py:103–150,190–219,292–318`; `apps/workload-api/templates/budget.yaml:1–17`; `apps/workload-api/README.md:15–29`.
- **Bằng chứng và tái lập.** Trên bản xuất Config, chạy thật `render_promotion()` với Git blobs mock. Manifest mặc định qua. Bật riêng `networkPolicy.enabled` hoặc `autoscaling.enabled` trong values trả `Protected chart renders an unexpected resource` vì guard yêu cầu đúng hai object. Dùng đúng bộ blobs mẫu cho `verify_workload_surface()` với `namespaceBudget.enabled=true` trả `Candidate chart renders an unexpected object`. Chart đặt tên quota và LimitRange là `workload-api-budget`, guard cho phép tên `workload-api`. Hàm cũng từ chối mọi trường Helm override trên Application, trong khi README mô tả sử dụng values overlay sau review.
- **Tác động.** Tùy chọn bảo mật/scale đã render lại có thể dừng promotion, rollback hoặc thay đổi cấu hình hợp lệ. Các test mặc định hai object và test lint riêng không kiểm chứng tổ hợp.
- **Khắc phục và chặn.** Dùng cùng chính sách manifest cho các mode đã duyệt, xác minh danh tính object đầy đủ và image giữ nguyên ngoài thao tác promotion. Ràng buộc effective values của Application vào exact merge, hoặc giới hạn công khai một chế độ duy nhất. Thêm ma trận promotion/rollback với NetworkPolicy, HPA, PDB, quota và TLS. **Chặn offline tích hợp, hosted activation và demo có các tuỳ chọn đó.**

### R1-02 — HIGH · Platform và Config · Portal ký đề xuất dựa trên requests khác Git

- **Vị trí.** Platform `portal/app.py:121–136,143–182,203–218`; `portal/github_client.py:192–236`; `optimizer/snapshot.py:131–182`. Config `apps/workload-api/templates/deployment.yaml:69–70`.
- **Bằng chứng và tái lập.** Dùng solver thật, snapshot demo và Flask test client với một deployer. Mock duy nhất hai GET GitHub, trả values theo đúng layout với request `2000m` và limit `2500m`. POST preview ba replica nhận HTTP 200 và proposal đã ký. Thay demand snapshot thành `2000m` cho cùng bằng chứng sức chứa khiến CBC và exhaustive trả `Infeasible`. Portal chỉ cập nhật replicas/RTT trong snapshot, đọc values sau khi giải, khóa diff và base mà chưa so requests. Submit giải lại từ snapshot và so vùng, nên bước đó cũng không ràng buộc demand với Git. Rollback placement bỏ qua solver theo nhánh `git-history`.
- **Tác động.** Có thể trình một phương án là khả thi dù Deployment render không vừa node. PR vẫn cần review riêng. Mốc freshness và base SHA không giải quyết sai khác giao diện này.
- **Khắc phục và chặn.** Đọc effective values ở immutable revision trước khi giải, chuẩn hóa requests theo chart, ràng buộc snapshot/build revision và kiểm tra lại khi submit. Với rollback, phân biệt khôi phục fields lịch sử với khả năng hiện hành và yêu cầu evidence/approval phù hợp. Thêm ca requests drift và target không còn node. **Chặn ghi portal và demo placement quan sát thực.**

### R1-03 — HIGH · Workload và Config · Luồng image-only PR thiếu writer

- **Vị trí.** Config `scripts/promote_image.py:71–89,293–350`, `scripts/check_promotion.py:309–323`; Workload `.github/workflows/promotion-preview.yml:4–47`; Platform `docs/PROMOTION_RUNBOOK.md:34–41`.
- **Bằng chứng và tái lập.** Đọc CLI, chạy dry-run fixture qua Config suite và truy vết Actions. Kết quả `propose` và tên nhánh là kế hoạch. CLI chỉ có dry-run/read-only. Hai repo không có đường App writer tạo nhánh và PR ảnh, trong khi guard yêu cầu đúng bot, branch và ý định. Writer placement của Platform chỉ sửa replica/region. Chế độ `--pin-digest` giới hạn dry-run.
- **Tác động.** Giữ được tư thế đóng của P0. Portal hoặc preview không thể thay thế việc tạo PR ảnh theo ADR. Một demo từ commit → receipt → bot PR → merge → Argo cần cơ chế đề xuất đã duyệt ngoài candidate hoặc hoàn thiện writer.
- **Khắc phục và chặn.** Chốt contract vận hành được phê duyệt. Nếu vẫn yêu cầu tự động, thêm writer chuyên biệt và test generation đổi, branch ngoại lai, retry và first pin, với quyền App và gate riêng. **Chặn mức hoàn chỉnh source P0 và kích hoạt hosted end-to-end.**

## Phát hiện bảo mật, tích hợp và chất lượng còn lại

### R1-04 — MEDIUM · Config và Workload · Bước trusted check thiếu đường đọc GHCR private

- **Vị trí.** Config `.github/workflows/trusted-promotion.yml:19–43`, `scripts/check_promotion.py:277–288,339–345`, `scripts/promote_image.py:190–228`; Workload `.github/workflows/promotion-preview.yml:36–47`.
- **Bằng chứng và tái lập.** Đối chiếu workflow và subprocess. Trusted check truyền token đọc API Workload cho `GitHubReader`. `registry_digest()` chủ động bỏ token đó trước khi gọi Buildx. Job không có bước GHCR login hoặc thiết lập credential store. Workload preview riêng có bước login nhưng hard-disabled và không dùng chung runner. Không thử kết nối GHCR hoặc suy đoán visibility thật.
- **Tác động.** Nếu package private, trusted check có thể fail closed khi kiểm manifest dù đã đọc được receipt. Mock registry hiện không phát hiện thiếu cơ chế xác thực runner.
- **Khắc phục và chặn.** Xác minh visibility. Với private, thêm quyền đọc package đã duyệt, chứng minh pull/tag+digest từ job bảo vệ và có ca auth thất bại. Giữ credential đọc riêng credential publish. **Chặn hosted khi package private hoặc quyền chưa xác minh.** [GitHub Packages container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

### R1-05 — MEDIUM · Workload · PR workflow có thể pass khi hai ca Flask bị bỏ qua

- **Vị trí.** `.github/workflows/ci.yml:16–25,54–82`; `tests/test_red_metrics.py:23,40`; `requirements.txt:1–2`.
- **Bằng chứng và tái lập.** Job PR chỉ cài PyYAML. Chạy `python -S -B -m unittest discover -s tests -v` với PyYAML cục bộ và không đưa Flask vào đường import. Kết quả 13 pass, 2 skipped, exit 0. Hai ca bị bỏ là HTTP/metrics và log redaction. Khi có Flask, cả 15 pass. Smoke sau push main kiểm `/` và `/healthz` chứ không kiểm `/metrics` hoặc log.
- **Tác động.** Một check xanh trên runner không có Flask không chứng minh hành vi ứng dụng hay giới hạn thông tin log.
- **Khắc phục và chặn.** Cài phụ thuộc test/runtime tái lập trong job PR, fail khi thiếu Flask và đưa smoke metrics vào gate tương ứng. **Chặn công nhận đầy đủ hosted regression.**

### R1-06 — MEDIUM · Platform · Giới hạn label giữa Terraform và inventory adapter khác nhau

- **Vị trí.** `infra/terraform/lab/variables.tf:178–197`, `infra/terraform/modules/ansible-inventory/variables.tf:61–73`, `infra/ansible/render_inventory.py:72–76`.
- **Bằng chứng và tái lập.** Thêm một `.tftest.hcl` chỉ trong bản sao review phụ, tái sử dụng mock/overrides của `compute-iam.tftest.hcl`. Đưa label `"xx-" + "a"*63 + "-1"` vào `worker.simulated_regions["k3s-agent1"]`. Lab mock plan chấp nhận và xuất label dài 68. Đưa cùng label vào fixture inventory v1 Profile B thì adapter báo `Invalid simulated placement region.`.
- **Tác động.** Input được chấp nhận trước provisioning nhưng không chuyển sang Ansible. Kubernetes chỉ cho label value tối đa 63 ký tự.
- **Khắc phục và chặn.** Đồng bộ validate ở Terraform lab, module inventory và adapter. Kiểm thêm ca biên 63/64 trong handoff. **Chặn các đầu vào lỗi. Profile mặc định vẫn render được.** [Kubernetes labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#syntax-and-character-set)

### R1-07 — MEDIUM · Platform · Journal có thể báo lỗi sau khi GitHub đã tạo PR

- **Vị trí.** `portal/app.py:69–88,219–229`; `portal/github_client.py:262–326`; `tests/test_portal_proposals.py:126–148`.
- **Bằng chứng và tái lập.** Dùng proposal hợp lệ trong Flask test client, mock writer trả PR 17, cho `os.fsync` của intent thành công và lần confirm ném `OSError`. Mock writer được gọi đúng một lần, response là HTTP 503 chung, không giữ proposal retry cùng ID. Lỗi GitHub đi qua nhánh 502 riêng và có cơ chế retry. Bản ghi journal không tự chứa timestamp.
- **Tác động.** Người dùng có thể tạo preview khác và phát sinh PR trùng sau lỗi lưu xác nhận. Journal cục bộ có intent nhưng kết quả cần đối chiếu riêng. Bằng chứng retained audit vẫn chưa có.
- **Khắc phục và chặn.** Tách trạng thái trước và sau mutation, giữ request ID và đường đối chiếu PR có cùng branch, thêm timestamp và kiểm thử lỗi lưu/khởi động lại. Review quyền và retention của audit sink. **Chặn writer dùng chung trước khi có đường đối chiếu tin cậy.**

### R1-08 — MEDIUM · Platform và Config · Chưa có đường TLS ingress hoàn chỉnh từ cấu hình lab

- **Vị trí.** Platform `infra/ansible/templates/k3s-config.yaml.j2:4–9`; Config `apps/workload-api/examples/private-lab.values.yaml:1–10`, `apps/workload-api/README.md:15–20`, `argocd/applications/workload-api.yaml:9–17`.
- **Bằng chứng và tái lập.** Render overlay private cho ra Ingress class `traefik` và peer NetworkPolicy theo label Traefik. Đối chiếu template K3s thấy disable `traefik` và `servicelb`. Không có controller, IngressClass hay tạo TLS Secret trong ba snapshot. README thừa nhận các đầu vào owner cần có. Đây là hạn chế tích hợp, không phải lỗi cú pháp Ingress.
- **Tác động.** ClusterIP qua đường private port-forward là demo mặc định khả thi sau khi lab hoạt động. Overlay TLS sẽ không tự phục vụ trên lab được bootstrap như hiện tại.
- **Khắc phục và chặn.** Chốt local proof với port-forward, hoặc thêm kế hoạch controller/private listener và certificate đã duyệt, test exact host/path và deny path. Phối hợp với R1-01 cho effective values. **Chặn demo TLS; không chặn HTTP loopback.** [K3s networking services](https://docs.k3s.io/networking/networking-services)

### R1-09 — MEDIUM · Platform và Config · Đường quan sát đến snapshot còn thao tác thủ công

- **Vị trí.** Platform `docs/MANUAL_AWS_GATES.md:19–29`, `optimizer/kubernetes_snapshot.py:120–181`, `optimizer/snapshot.py:96–125`, `infra/ansible/render_inventory.py:86–91`; Config `observability/metrics/stack.values.yaml:21–43`.
- **Bằng chứng và tái lập.** Đọc import/entry points và gate. Có adapter NodeList/PodList đã lưu, còn metrics, RTT và pricing chờ operator chuẩn hóa JSON. Không có path truy vấn Prometheus hoặc script tạo observed snapshot từ một bộ export. Inventory chứa AZ nhưng renderer không đưa AZ/Region vật lý vào label trên node. Optimizer đọc label topology chuẩn nếu export có, có thể trả null nếu K3s không cung cấp label đó. Fixture có label mô phỏng và metadata vật lý giả lập tách biệt.
- **Tác động.** Báo cáo mô phỏng có thể tái lập. Demo live chưa có chuỗi evidence biết dữ liệu lấy từ đâu, cùng thời điểm, hoặc cách liên hệ với địa điểm AWS thật. Chưa chứng minh kết quả gán Pod thực.
- **Khắc phục và chặn.** Viết luồng chuẩn hóa export có timestamp, provenance, mapping từ inventory đã duyệt và ca thiếu keys. Đặt acceptance rõ cho snapshot cùng revision/cửa sổ quan sát. **Chặn demo observed end-to-end. Không chặn benchmark fixture.**

### R1-10 — MEDIUM · Platform · Test merge-order chạy đường GitHub client cũ

- **Vị trí.** `tests/test_promotion_placement_contract.py:12,25–37`; `portal/github_client.py:56–143,216–236,273–326`; `portal/app.py:166,214–221`.
- **Bằng chứng và tái lập.** Truy vết import. Suite merge-order dùng `create_placement_pull_request()` với branch UUID. Portal hiện dùng `prepare_change()` và `submit_change()`. Suite portal kiểm các mock riêng, còn merge-order trên cùng file Config không qua flow đang phục vụ người dùng. Case có tên ràng buộc actor hiện chỉ gửi proposal không hợp lệ trong `tests/test_portal_proposals.py:108–113`. R1 kiểm bổ sung proposal hợp lệ của deployer khác và nhận 403.
- **Tác động.** Một số test liên repo vẫn pass sau khi hành vi đường production đổi. Hàm cũ có ít kiểm soát hơn và vẫn hiện như API khả dụng.
- **Khắc phục và chặn.** Đưa cả hai merge order qua `prepare_change` và kiểm exact payload của `submit_change`. Giữ ca actor sai với chữ ký hợp lệ. Xác nhận không có caller khác trước khi bỏ hoặc đánh dấu legacy. **Chặn công nhận đủ coverage, không phải bằng chứng có bypass đang hoạt động.**

### R1-11 — LOW · Platform · Tài liệu trong SHA không đầy đủ và còn mô tả baseline cũ

- **Vị trí.** `docs/FINAL_REVIEW.md:26`; `infra/terraform/README.md:3`; `docs/ARCHITECTURE.md:28–44`; `docs/SECURITY.md:14–20`; `docs/ROADMAP.md:5–15`; `docs/PROJECT_STATE.md:18–35`.
- **Bằng chứng và tái lập.** `git ls-tree -r --name-only 9a807b6 -- docs` không có AWS_LAB_DESIGN và ADR 0003/0004. Kiểm link trên archive thấy hai đường dẫn AWS_LAB_DESIGN hỏng. Các tài liệu tracked mô tả portal cũ dùng branch UUID, thiếu login và delivery bằng tag, còn báo cáo cuối và code thể hiện kiến trúc mới. Một phần nội dung mới tồn tại ở checkout bẩn.
- **Tác động.** Người lấy đúng SHA không nhận đủ căn cứ thiết kế và có thể dùng sai mô hình kiểm soát hoặc lệnh vận hành.
- **Khắc phục và chặn.** Đóng gói các tài liệu được duyệt cùng candidate, đánh dấu rõ ngày và phạm vi baseline, kiểm link trên clean export. Ghi demo offline và live thành hai đường riêng trong CV/portfolio. **Chặn bàn giao tài liệu hoàn chỉnh, không chặn chạy test.**

### R1-12 — LOW · Workload · Build đầu vào thay đổi theo thời điểm

- **Vị trí.** `Dockerfile:1–6`, `requirements.txt:1–2`, `.github/workflows/ci.yml:41–52,115–138,173–210`.
- **Bằng chứng và tái lập.** Đọc Dockerfile. Base dùng tag `python:3.12-slim`, Flask/Gunicorn theo range, và không có lock với hashes trong SHA. Workflow bảo vệ tính nhất quán giữa archive được test, scan và publish của một run. Điều đó không cố định ảnh khi build lại cùng source từ upstream mới.
- **Tác động.** Rebuild cùng SHA có thể nhận phiên bản khác. First-writer gate giảm khả năng ghi đè tag đã xuất bản. Audit và khôi phục cần giữ digest/receipt và artefact gốc.
- **Khắc phục và chặn.** Dùng base digest và khóa dependency/hashes có quy trình cập nhật, sau đó thực hiện scan/SBOM cho exact artefact. **Chặn tiêu chí reproducibility production, không chặn học lab cục bộ.**

Không xác nhận phát hiện CRITICAL trên nguồn và fixture đã xem. Không có bằng chứng trạng thái hosted hiện tại. OIDC có thể dùng xác thực TLS của endpoint trực tiếp để kiểm issuer trong Authorization Code Flow theo đặc tả. Điều đó phù hợp thiết kế hiện tại trong mô hình tin cậy được khai báo. Cần kiểm issuer, proxy, cookie, token endpoint, ACL và audit trong môi trường tích hợp trước khi mở dịch vụ. [OpenID Connect Core §3.1.3.7](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)

## Kết quả chạy thực tế

| Khu vực | Lệnh hoặc phép thử | Kết quả |
| --- | --- | --- |
| Terraform | `python -B scripts/terraform_offline.py --provider-mirror <approved-existing-local-mirror>` | **PASS 111/111**. Lab 49, bootstrap 14, inventory 9, compute 11, IAM 8, network 8, security 12. Format và 7 validate đều qua. Terraform 1.15.5 Windows amd64, AWS provider khóa 6.73.0. |
| Bootstrap Python | `python -B -m unittest discover -s infra/terraform/bootstrap/tests -v` | **PASS 7/7**. Hợp đồng partial backend, file create-only và policy/render. |
| Platform Python | `python -B -m unittest discover -s tests -v` với hai biến checkout trỏ vào archive Config/Workload | **PASS 52/52**, gồm các ca Ansible nội dung, phục hồi SQLite giả lập, PR/IdP/Argo mock và contract liên repo. |
| Config Python | Cùng lệnh từ Config | **PASS 55/55**, dùng Helm 4.3.2 trong các ca render. |
| Workload Python | Cùng lệnh từ Workload với Flask và PyYAML hiện có | **PASS 15/15**. Mô phỏng môi trường PR chỉ PyYAML cho 13 pass và 2 skip. |
| Helm và policy | `helm lint` cho workload mặc định, private, metrics và demo. `helm template workload-api ./apps/workload-api` rồi chạy `scripts/check_deployment_policies.py` | **PASS** 4 lượt lint và policy của Deployment mặc định. R1-01 tái hiện riêng. |
| HTTP local | Bind Werkzeug WSGI tại `127.0.0.1` cổng tạm, GET `/`, `/healthz`, `/metrics` | **PASS** ba HTTP 200 và kiểm nội dung cơ bản. Docker daemon named pipe không tồn tại tại thời điểm kiểm. Gunicorn/Linux image chưa chạy. |
| Runbooks | Git Bash `-n`, PowerShell Parser và `node --input-type=module --check` | **PASS** 10 khối Bash recovery, 26 khối PowerShell và cú pháp JS k6. Không thực thi lệnh vận hành hoặc phát tải. |
| Ca thêm | Mock-only Terraform witness; Helm với Git blobs mock; Flask với GitHub/Argo doubles | **Đã tái hiện** R1-01/02/06/07. Ca gắn proposal với owner trả 403 khi đổi actor. Các witness không tính vào tổng suite của checkpoint. |
| Công cụ/runtime khác | Ansible CLI, Docker build, charts upstream đầy đủ, `actionlint`, `gitleaks`, `promtool`, Alloy và k6 | **BLOCKED / NOT RUN**. Chưa sẵn công cụ, local daemon hoặc gói đã duyệt trong phạm vi kiểm tra. Không cài thêm. |
| Hosted và cloud | GitHub event/required check, registry auth, Kubernetes, real Terraform/provider, S3 native lock, SSM, restore và SLO | **NOT RUN**. Thuộc gate được phê duyệt riêng. |

**Cách đếm.** 14 ca HCL bootstrap nằm trong 111. Bảy ca Python ở thư mục bootstrap riêng, không thuộc 52 Platform Python và không nằm trong 111 HCL. Hai nhóm bootstrap có chủ đề chung như state key, isolation và policy, nên số ca không đồng nghĩa số kiểm soát bảo mật độc lập. Phạm vi 52 + 55 + 15 là 122 lượt kiểm thử Python theo repo, có hợp đồng chung được kiểm từ nhiều phía.

**An toàn Terraform.** Trước khi chạy, kiểm nguồn archive không có backend phụ, data sources, provisioner hay module từ xa trong suite. Runner copy nguồn, kiểm `command = plan` và mock AWS, dùng mirror và lock read-only, `init -backend=false`, loại setting AWS/TF kế thừa, tạo file AWS rỗng và thay S3 backend bằng local chỉ trong scratch sau validate. Kiểm định provider này giới hạn ở cây source đã đọc. Runner dùng scanner HCL đơn giản và package cục bộ đáng tin cậy. [Lệnh và phạm vi](../scripts/README.md)

**Observability.** Đối chiếu values upstream cho Loki 18.7.6 và kube-prometheus-stack 85.0.0. Đã kiểm sự hiện diện của mode Monolithic và cơ chế selector theo Helm release. Lệnh render local chỉ bao phủ chart Workload cùng cấu hình static observability. Chưa chứng minh DNS/label/port Loki thực, labels scrape của operator, rule PromQL, Alloy filter, NetworkPolicy deny, disk retention hoặc tải. [Loki values](https://raw.githubusercontent.com/grafana-community/helm-charts/loki-18.7.6/charts/loki/values.yaml) · [Prometheus stack values](https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-prometheus-stack-85.0.0/charts/kube-prometheus-stack/values.yaml)

### Kiểm chứng benchmark

Chạy `python -B -m benchmarks.compare_algorithms --snapshot optimizer/data/placement_snapshot_v1.json --as-of 2026-11-26T12:01:00Z --repeats 7`. CBC solver package PuLP 3.3.0, một thread và seed 1. Với biến nhị phân theo replica/node, mỗi replica chọn đúng một node. Tổng CPU, memory và pod slots không vượt free capacity theo node. Replica cùng workload cùng vùng selector. Tập candidate lọc trạng thái node, RTT, taint và bằng chứng cần thiết. Objective chung cộng cost estimate, chuyển vùng và peak pressure có trọng số. Scorer kiểm lại nghiệm trả về trước khi tính điểm. Exhaustive có giới hạn tổ hợp và greedy không chứng minh vô nghiệm.

| Phương pháp | Trạng thái | Objective | Median tại lần R1 |
| --- | --- | ---: | ---: |
| CBC | Optimal | 0,724 | 47,355 ms |
| Greedy | Feasible | 0,738 | 0,013 ms |
| Exhaustive | Optimal | 0,724 | 0,029 ms |

Ca bổ sung đưa demand lên 2000 mCPU và giới hạn một vùng không có node. Mỗi ca cho kết quả CBC/exhaustive infeasible, greedy no solution. Snapshot ngoài cửa sổ 300 giây bị từ chối. Chênh 1,934% là điểm mô hình trên fixture nhỏ, không đo tiết kiệm AWS hoặc năng lực production. Với mode observed, data được cung cấp thủ công. Co-location, dung lượng thực, disruption, storage, affinity, quota và race scheduler cần xác minh riêng.

## Thứ tự xử lý và kế hoạch kiểm chứng runtime cục bộ

1. **Ưu tiên 1 — Khóa các sai khác offline.** Dùng R1-01/02/06 làm ca fail trước khi sửa. Kiểm chart qua guard với exact candidate và nối Git requests với snapshot. Kiểm lại ca bảo vệ trust và actor, test contract qua đường portal hiện hành. Chuẩn hóa các tài liệu còn ở ngoài commit.
2. **Ưu tiên 2 — Kiểm workload/portal trong sandbox.** Tạo môi trường Python được khóa và runtime Linux được phê duyệt, dùng runner dành riêng, port loopback trống và image artefact cục bộ. Build/chạy image non-root và read-only như chart, smoke `/`, `/healthz`, `/metrics`, worker và batch. Chạy portal với IdP HTTPS thử nghiệm và mock GitHub/Argo. Kiểm expired/stale/nonce/role/CSRF, retry after API success và audit failure.
3. **Ưu tiên 3 — Kubernetes cục bộ chuyên dụng.** Chỉ dùng context mới đã duyệt, riêng với cluster hiện có; vào cluster local không dùng AWS. Render gói upstream đã kiểm hash, parser PromQL/Alloy và manifest schema. Dựng một server và hai agent để kiểm workload placement, HPA/PDB, NetworkPolicy, manual sync, digest, worker/CronJob và private ingress nếu nằm trong demo. Kiểm publish/preview vẫn tắt. Ghi bằng chứng fail/recover và rollback bằng Git cục bộ. Diễn tập Ansible phiên bản duyệt trong VM Linux trước, SSM transport thật tiếp tục phụ thuộc gate AWS.
4. **Ưu tiên 4 — Chốt đường hosted và owner.** Chứng minh writer hoặc quy trình đề xuất riêng, private registry read, renderer, review recheck và provenance của required check. Workflow trusted hiện có triggers PR mở, mở lại, synchronize và ready_for_review; cần diễn tập cách chạy lại sau review mà vẫn gắn exact head/base. Sau khi có bằng chứng và ủy quyền riêng, dùng gate P0.5 rồi AWS-11–16 theo runbook. Reviewer R1 không thực thi các bước đó. [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target) · [Manual gates](MANUAL_AWS_GATES.md)

**Phụ thuộc còn lại.** Linux Ansible, Docker hoặc môi trường chạy container cô lập, K3s/Argo compatible và máy test riêng, chart packages và collector/scanner binaries đã duyệt, private registry access, GitHub App/ruleset/required-check evidence, IdP và TLS, audit retention, AWS identity/budget, AMI/AZ quotas và transfer bucket, evidence native state lock/recovery. Giữ nguyên hai hard stop ở Workload và `frozen: true` ở Config trong khi xác minh. [Kịch bản demo](DEMONSTRATION.md) · [Quality gates](QUALITY_GATES.md)

## Phán quyết readiness

| Hạng mục | Verdict | Căn cứ |
| --- | --- | --- |
| Triển khai mã nguồn | **NOT READY** | Mã chính hiện diện. R1-01/02/03 là lỗ hổng chức năng trên luồng tích hợp. |
| Tích hợp offline | **NOT READY** | Các suite gốc pass. Các ca kết hợp ngoài suite tái hiện lỗi giữa Config/promotion, Git/snapshot và Terraform/Ansible. |
| Kiểm chứng local runtime | **NOT READY** | Workload HTTP loopback đã pass. Thiếu daemon và môi trường K3s/Ansible/observability test riêng để kiểm toàn hệ thống. |
| Kích hoạt CI/CD hosted | **NOT READY** | Hard stop vẫn có hiệu lực. Cần khép writer/runner auth, review check provenance và PR test bắt buộc. |
| Triển khai AWS | **NOT READY** | Kiểm mock và review source. Gate owner và integration runtime còn pending. |
| Trình diễn portfolio | **NOT READY** | Có thể trình bày fixture, mock, HTTP smoke và benchmark với nhãn phạm vi rõ. Chưa trình diễn được vòng đời tích hợp có hosted, runtime và recovery evidence. |
| Production | **NOT READY** | Cần sửa các điểm chặn, chứng minh quyền và chuỗi release, đo SLO phục hồi, kiểm môi trường đa dạng hơn và xử lý giới hạn một server/một AZ. |
