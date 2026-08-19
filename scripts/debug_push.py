import json, subprocess, sys, base64, os

COMMIT_SHA = "07ea392d9d1e597b61229abe935d1240f47cdb67"
REPO = "repos/xymdcyy/settlement-reconciliation"
GIT_DIR = r"D:\结算对账中心"

# 获取 tree 内容
r = subprocess.run(["git", "ls-tree", "-r", "-z", f"{COMMIT_SHA}^{{tree}}"], capture_output=True, cwd=GIT_DIR)
raw = r.stdout
entries_raw = raw.split(b"\x00")
entries = []
for e in entries_raw:
    s = e.decode("utf-8")
    if not s.strip():
        continue
    if "\t" in s:
        meta, path = s.split("\t", 1)
        parts = meta.split()
        entries.append((parts[0], parts[1], parts[2], path))

print(f"Total entries: {len(entries)}")

# 检查哪些 blob 不在远程
for mode, obj_type, obj_sha, path in entries:
    if obj_type != "blob":
        continue
    r = subprocess.run(
        ["gh", "api", f"{REPO}/git/blobs/{obj_sha}", "--jq", ".sha"],
        capture_output=True, timeout=10
    )
    if r.returncode != 0:
        # 上传 blob
        r2 = subprocess.run(["git", "cat-file", "-p", obj_sha], capture_output=True, cwd=GIT_DIR)
        content = r2.stdout
        is_binary = False
        try:
            content.decode("utf-8")
        except:
            is_binary = True
        payload = {
            "content": base64.b64encode(content).decode() if is_binary else content.decode("utf-8", errors="replace"),
            "encoding": "base64" if is_binary else "utf-8",
        }
        r3 = subprocess.run(
            ["gh", "api", f"{REPO}/git/blobs", "--input", "-", "--jq", ".sha"],
            input=json.dumps(payload).encode(),
            capture_output=True, timeout=30
        )
        if r3.returncode == 0:
            print(f"  Uploaded: {path} -> {obj_sha}")
        else:
            print(f"  FAILED: {path} -> {obj_sha}: {r3.stderr.decode()[:200]}")

print("\nAll blobs uploaded. Now testing tree creation...")

# 测试创建 tree
tree_data = [{"path": path, "mode": mode, "type": obj_type, "sha": obj_sha}
             for mode, obj_type, obj_sha, path in entries]

# 尝试小 tree 测试
small_tree = tree_data[:3]
r = subprocess.run(
    ["gh", "api", f"{REPO}/git/trees", "--input", "-"],
    input=json.dumps({"tree": small_tree}).encode(),
    capture_output=True, timeout=30
)
print(f"Small tree test: status={r.returncode}")
if r.returncode != 0:
    print(f"  stderr: {r.stderr.decode()[:500]}")
    print(f"  payload: {json.dumps(small_tree, ensure_ascii=False)[:300]}")
else:
    print(f"  Result: {r.stdout.decode()[:200]}")

# 尝试完整 tree 但分块发送
print(f"\nFull tree: {len(tree_data)} entries")
r = subprocess.run(
    ["gh", "api", f"{REPO}/git/trees", "--input", "-"],
    input=json.dumps({"tree": tree_data}).encode(),
    capture_output=True, timeout=60
)
print(f"Full tree: status={r.returncode}")
if r.returncode != 0:
    print(f"  stderr: {r.stderr.decode()[:500]}")
else:
    print(f"  Result: {r.stdout.decode()[:200]}")