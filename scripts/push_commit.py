import json, subprocess, sys, base64, os, hashlib, zlib
from datetime import datetime, timezone

COMMIT_SHA = "d640aad0b24dc3fba46903204d03b8cf6b943ed7"
PARENT_SHA = "c5019ae10373021de69281bf4185023f54a817a9"
REPO = "repos/xymdcyy/settlement-reconciliation"
GIT_DIR = r"D:\结算对账中心"


def gh_api(endpoint, input_data=None, method=None):
    parts = ["gh", "api", f"{REPO}/git/{endpoint}"]
    if method:
        parts.extend(["-X", method])
    if input_data is not None:
        parts.extend(["--input", "-"])
        r = subprocess.run(parts, input=json.dumps(input_data).encode(), capture_output=True, timeout=60)
    else:
        r = subprocess.run(parts, capture_output=True, timeout=60)
    return r


def main():
    r = subprocess.run(["git", "rev-parse", f"{COMMIT_SHA}^{{tree}}"], capture_output=True, cwd=GIT_DIR)
    tree_sha = r.stdout.decode().strip()
    print(f"Tree: {tree_sha}")

    r = subprocess.run(["git", "ls-tree", "-r", "-z", tree_sha], capture_output=True, cwd=GIT_DIR)
    entries = []
    for e in r.stdout.split(b"\x00"):
        s = e.decode("utf-8")
        if not s.strip() or "\t" not in s:
            continue
        meta, path = s.split("\t", 1)
        parts = meta.split()
        entries.append((parts[0], parts[1], parts[2], path))
    print(f"Entries: {len(entries)}")

    for i, (mode, obj_type, obj_sha, path) in enumerate(entries):
        if obj_type != "blob":
            continue
        r = gh_api(f"blobs/{obj_sha}")
        if r.returncode == 0:
            continue
        r2 = subprocess.run(["git", "cat-file", "-p", obj_sha], capture_output=True, cwd=GIT_DIR)
        content = r2.stdout
        try:
            content.decode("utf-8")
            payload = {"content": content.decode("utf-8", errors="replace"), "encoding": "utf-8"}
        except:
            payload = {"content": base64.b64encode(content).decode(), "encoding": "base64"}
        r3 = gh_api("blobs", payload)
        if r3.returncode != 0:
            print(f"  Failed: {path}: {r3.stderr.decode()[:200]}")
            sys.exit(1)
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(entries)}")

    tree_data = [{"path": p, "mode": m, "type": t, "sha": s} for m, t, s, p in entries]
    r = gh_api("trees", {"tree": tree_data})
    if r.returncode != 0:
        print(f"Tree creation failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    new_tree = json.loads(r.stdout)["sha"]
    print(f"New tree: {new_tree}")

    commit_payload = {
        "message": "fix: 代码审查 15 项问题修复\n\n修复清单：\n1. export_service 手动匹配 (manual) 计入已匹配\n2. WorkspacePage 读取路由参数，历史页面导航生效\n3. Decimal 假零检查改为 is not None，0 值正常显示\n4. settlements[r.settlement_id] 改为 .get() 防 KeyError\n5. StreamingResponse 改为 Response，避免 .xlsx 被截断\n6. 导出文件名 RFC 5987 编码，兼容所有浏览器\n7. 前端导出使用 axios 而非原生 a 标签，保留错误处理\n8. 前端导出 a.download 不再覆盖后端文件名\n9. 空 customer_ids 集合 IN() 查询保护\n10. 历史查询 matched_count 计入 manual 状态\n11. /history 端点绑定 response_model=HistoryResponse\n12. bare except 改为 except Exception\n13. 空数据工作表使用固定列结构（columns=）而非单列 fallback\n14. push_commit.py strptime 时区格式兼容 Z 和 +08:00\n15. 新增 6 个导出服务测试覆盖修复\n\n52 个测试通过，前端构建通过",
        "tree": new_tree,
        "parents": [PARENT_SHA],
        "author": {"name": "XuYiming", "email": "1378936642@qq.com", "date": "2026-08-19T21:30:23+08:00"},
        "committer": {"name": "XuYiming", "email": "1378936642@qq.com", "date": "2026-08-19T21:30:23+08:00"},
    }
    r = gh_api("commits", commit_payload)
    if r.returncode != 0:
        print(f"Commit creation failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    remote_sha = json.loads(r.stdout)["sha"]
    print(f"Remote commit: {remote_sha}")

    r = gh_api("refs/heads/master", {"sha": remote_sha, "force": True}, method="PATCH")
    if r.returncode != 0:
        print(f"Ref update failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    print(f"Ref updated!")

    r = gh_api(f"commits/{remote_sha}")
    data = json.loads(r.stdout)
    tree, parent = data["tree"]["sha"], data["parents"][0]["sha"]
    auth, comm = data["author"], data["committer"]
    msg = data["message"]

    def to_ts(d):
        raw = d["date"]
        if raw.endswith("Z"):
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return f'{int(dt.timestamp())} +0800'

    content = f'tree {tree}\nparent {parent}\n'
    content += f'author {auth["name"]} <{auth["email"]}> {to_ts(auth)}\n'
    content += f'committer {comm["name"]} <{comm["email"]}> {to_ts(comm)}\n'
    content += f'\n{msg}'

    raw = f'commit {len(content.encode())}\0{content}'.encode()
    sha = hashlib.sha1(raw).hexdigest()
    assert sha == remote_sha, f"SHA mismatch: {sha}"

    obj_file = os.path.join(GIT_DIR, ".git", "objects", sha[:2], sha[2:])
    os.makedirs(os.path.dirname(obj_file), exist_ok=True)
    if os.path.isfile(obj_file):
        os.remove(obj_file)
    with open(obj_file, "wb") as f:
        f.write(zlib.compress(raw))
    subprocess.run(["git", "update-ref", "refs/heads/master", sha], cwd=GIT_DIR)
    print(f"Local synced to {sha}")


if __name__ == "__main__":
    main()