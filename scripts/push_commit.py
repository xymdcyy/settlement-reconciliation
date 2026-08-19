import json, subprocess, sys, base64, os, hashlib, zlib
from datetime import datetime, timezone

COMMIT_SHA = "27a1b78f836c144e784f999f5bc8142643f1a64f"
PARENT_SHA = "98451c4e8d3cc3c3cb87da4c4983a7bf83112ee1"
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
    # 获取 tree
    r = subprocess.run(["git", "rev-parse", f"{COMMIT_SHA}^{{tree}}"], capture_output=True, cwd=GIT_DIR)
    tree_sha = r.stdout.decode().strip()
    print(f"Tree: {tree_sha}")

    # 获取 tree entries
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

    # 上传缺失的 blob
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

    # 创建 tree
    tree_data = [{"path": p, "mode": m, "type": t, "sha": s} for m, t, s, p in entries]
    r = gh_api("trees", {"tree": tree_data})
    if r.returncode != 0:
        print(f"Tree creation failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    new_tree = json.loads(r.stdout)["sha"]
    print(f"New tree: {new_tree}")

    # 创建 commit
    commit_payload = {
        "message": "feat: 报表导出 + 历史查询\n\n- 导出服务：5 个工作表 Excel（汇总、匹配明细、我方未匹配、客户未匹配、差异明细）\n- GET /api/reconciliation/export 导出 API\n- GET /api/reconciliation/history 历史查询 API\n- 历史页面：客户+月份筛选，卡片展示，点击跳转工作台，导出按钮\n- 46 个测试通过，前端构建通过",
        "tree": new_tree,
        "parents": [PARENT_SHA],
        "author": {"name": "XuYiming", "email": "1378936642@qq.com", "date": "2026-08-19T21:05:16+08:00"},
        "committer": {"name": "XuYiming", "email": "1378936642@qq.com", "date": "2026-08-19T21:05:16+08:00"},
    }
    r = gh_api("commits", commit_payload)
    if r.returncode != 0:
        print(f"Commit creation failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    remote_sha = json.loads(r.stdout)["sha"]
    print(f"Remote commit: {remote_sha}")

    # 更新 ref
    r = gh_api("refs/heads/master", {"sha": remote_sha, "force": True}, method="PATCH")
    if r.returncode != 0:
        print(f"Ref update failed: {r.stderr.decode()[:300]}")
        sys.exit(1)
    print(f"Ref updated!")

    # 同步本地
    r = gh_api(f"commits/{remote_sha}")
    data = json.loads(r.stdout)
    tree, parent = data["tree"]["sha"], data["parents"][0]["sha"]
    auth, comm = data["author"], data["committer"]
    msg = data["message"]

    def to_ts(d):
        # 支持 '2026-08-19T12:17:51Z' 和 '2026-08-19T20:27:54+08:00' 两种格式
        raw = d["date"]
        if raw.endswith("Z"):
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        else:
            # 去掉末尾时区偏移，只保留 UTC 时间
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