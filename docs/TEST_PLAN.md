# Kế hoạch kiểm chứng P0–P7

Các ứng viên gốc là Platform `9a807b6`, Config `59a61aa`, Workload `626f62b`. Chạy công việc trên worktree branch `fix/p0-p7-verification` của từng repo. Đọc [review R1](INDEPENDENT_FINAL_REVIEW.md) để tìm ca tái hiện và [sổ lỗi](DEFECT_REGISTER.md) để theo dõi kết quả.

| Nhóm ca | Phép thử | Tiêu chí nghiệm thu |
| --- | --- | --- |
| BASE | So SHA, index, trạng thái worktree; chạy baseline trên bản xuất bằng `git archive`. | Đúng ba commit, 111 mock Terraform và Python 7/52/55/15. |
| TF-IAC | Runner cô lập dùng local mirror, validate và mock plan cho từng root/module. Test cả ba profile, worker thứ hai, native state policy, giới hạn label 63/64. | Zero real provider plans. Chấp nhận 63 và từ chối 64 trước handoff. Khóa và policy trỏ đúng môi trường. |
| GH-CONFIG | Helm lint/template, guard theo exact Git tree và nhóm tùy chọn, manifest lạ, promotion/rollback, scope writer và retry. | Chỉ tài nguyên/name/namespace được phép, đúng ảnh, chỉ values thay trong PR image, stale/frozen/foreign bị từ chối. Registry thật vẫn ở gate. |
| GH-WORKLOAD | Unit test, workflow policy, bộ test với Flask, kiểm hard stop và action pin. | Flask bắt buộc trên PR, publisher/preview đóng. |
| WEB | WSGI loopback của Workload, HTTPS loopback của Portal, token endpoint test và HTTP doubles cho GitHub/Argo. | Health/metrics 200, PKCE/state/nonce/cookie, viewer/unauthorized bị từ chối, preview/rollback tuân tài nguyên Git, audit failure giữ request. |
| OPT | Snapshot v1, NodeMetricsList, export đã làm sạch, stale/invalid/insufficient/incompatible, CBC/greedy/exhaustive 7 lần. | Reproduce objective trên fixture, không vượt budget, hai-worker placement có tính khả thi trong mô hình, mode/revision rõ. |
| OS-K3S | Ansible syntax/lint và test Ubuntu disposable khi có máy; verify inventory, pinned binary, tokens/idempotency và Argo bootstrap. | Lần chạy thứ hai an toàn, không lộ token. SSM thật thuộc AWS owner gate. |
| LOCAL-K3S | Cluster k3d được đặt tên riêng, kubeconfig riêng, 1 server/2 agents. Load image cục bộ, Git source cô lập. | 3 Ready, queries/RBAC/Pod Security/CNI ingress và egress, traffic TLS nếu đã có controller, HPA/PDB, reviewed sync và rollback. |
| OBS-FAIL | Render đúng gói chart pin, chạy promtool/Alloy/k6 trên môi trường local, test rule/collector, endpoint và recovery. | Scrape, ingestion, dashboard/alert local receiver, workload kill/drain, backup restore và overhead có bằng chứng. |
| SECURITY | Parse code/YAML/shell, pip check, scan secret/dependency/container bằng các công cụ sẵn có. | Bảo vệ permission, không secret trong candidate, ghi phạm vi pattern scan và kết quả scanner riêng. |

## Lệnh có thể chạy lại mà không dùng AWS

- Từ mỗi worktree chạy `python -B -m unittest discover -s tests -v`. Dùng venv có Flask, Requests, PuLP/CBC, Jinja2 và PyYAML. Với Platform, trỏ `PLATFORM_CONFIG_CHECKOUT` và `PLATFORM_WORKLOAD_CHECKOUT` đến các worktree đã kiểm SHA.
- Từ Platform chạy `python -B scripts/terraform_offline.py --provider-mirror <local-locked-provider-mirror>` rồi `python -B -m unittest discover -s infra/terraform/bootstrap/tests -v`.
- Từ Config chạy `helm lint apps/workload-api`, `helm lint apps/workload-api -f apps/workload-api/examples/private-lab.values.yaml`, `helm lint apps/workload-api -f observability/metrics/private-workload.values.yaml` và `helm lint apps/demo-jobs`. Dùng `helm template workload-api ./apps/workload-api` ra tệp tạm rồi chạy `python -B scripts/check_deployment_policies.py <rendered.yaml>`. Render theo client mode với kubeconfig rỗng/cô lập.
- Từ Platform chạy `python -B -m benchmarks.compare_algorithms --case baseline --repeats 7`, rồi `--case infeasible` và `--snapshot optimizer/data/placement_snapshot_v1.json --as-of 2026-11-26T12:01:00Z --repeats 7`.
- Với smoke Portal, dùng TLS loopback và CA tạm, cấp code/nonce/PKCE bằng token endpoint test rồi kiểm cookie và RBAC. Với Workload, dùng WSGI loopback trên cổng động và HTTP assertions tới ba routes.
- Khi runtime có sẵn, mỗi lệnh kubectl phải mang kubeconfig và context của lab disposable mới. Dùng `helm ... --kubeconfig <isolated-file> --kube-context <local-only-context>`. Kiểm context, daemon đã được phê duyệt, cluster name và source trước khi deploy hoặc cleanup. Owner AWS và GitHub hosted tiếp tục dùng các gate riêng. [Gate](MANUAL_AWS_GATES.md)

## Tái lập portal TLS loopback

Từ Platform, tạo thư mục tạm mới và đặt biến VERIFY_TMP trỏ tới đó. Tạo test certificate có SAN 127.0.0.1.

```powershell
$env:VERIFY_TMP = (New-Item -ItemType Directory (Join-Path ([IO.Path]::GetTempPath()) ('idp-review-' + [guid]::NewGuid()))).FullName
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' -keyout (Join-Path $env:VERIFY_TMP 'review-key.pem') -out (Join-Path $env:VERIFY_TMP 'review-cert.pem')
python -B -m scripts.verify_portal_loopback
```

Cả hai listener dùng cổng loopback động và dừng sau khi chạy. Chỉ dùng chứng chỉ tạm tại lab thử nghiệm. Không đưa key vào kho và không dùng key này bên ngoài fixture.


## Tái lập Workload HTTP loopback

Từ Workload, dùng venv kiểm thử đã có Flask và Werkzeug. Đưa đoạn sau vào tệp .py tạm bên ngoài repo rồi chạy `python -B <tệp-tạm>` với `PYTHONPATH` trỏ đến thư mục Workload. Tiến trình lắng nghe cổng động và dừng khi kiểm xong.

```python
import json
from threading import Thread
from urllib.request import ProxyHandler, build_opener

from werkzeug.serving import make_server
from workload_api.app import app

server = make_server("127.0.0.1", 0, app)
worker = Thread(target=server.serve_forever, daemon=True)
worker.start()
opener = build_opener(ProxyHandler({}))

def get(path):
    with opener.open(f"http://127.0.0.1:{server.server_port}{path}", timeout=3) as response:
        assert response.status == 200
        return response.read()

try:
    assert json.loads(get("/"))["app"] == "workload-api"
    assert json.loads(get("/healthz")) == {"status": "ok"}
    assert b"workload_api_http_requests_total" in get("/metrics")
finally:
    server.shutdown()
    server.server_close()
    worker.join(timeout=3)
```
