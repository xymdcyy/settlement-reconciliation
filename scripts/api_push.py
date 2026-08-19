"""通过 GitHub API 推送代码（git push 的 443 端口被防火墙拦截时使用）"""
import json, subprocess, sys, base64

REPO = "repos/xymdcyy/settlement-reconciliation"

def gh(*args, input_data=None):
    cmd = ["gh", "api"] + list(args)
    stdin = json.dumps(input_data) if input_data else None
    r = subprocess.run(cmd, capture_output=True, text=True, input=stdin)
    if r.returncode != 0:
        print(f"gh error: {r.stderr[:200]}")
        return None
    return json.loads(r.stdout)

# 1. Get remote HEAD
r = gh(f"{REPO}/git/refs/heads/master", method="GET")
if not r:
    sys.exit(1)
remote_sha = r["object"]["sha"]
print(f"远程: {remote_sha}")

# 2. Get local files
lines = subprocess.run(["git", "ls-tree", "-r", "HEAD"],
                       capture_output=True, text=True).stdout.strip().split("\n")
print(f"本地文件: {len(lines)}")

# 3. Upload blobs
tree_items = []
for line in lines:
    if not line.strip():
        continue
    parts = line.split()
    mode, type_, sha = parts[0], parts[1], parts[2]
    path = " ".join(parts[3:])
    content = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True).stdout
    b64 = base64.b64encode(content).decode()
    blob = gh(f"{REPO}/git/blobs",
              input_data={"content": b64, "encoding": "base64"})
    if blob:
        tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})

print(f"上传: {len(tree_items)} blobs")

# 4. Create tree
new_tree = gh(f"{REPO}/git/trees", input_data={"tree": tree_items})
if not new_tree:
    sys.exit(1)
print(f"Tree: {new_tree['sha']}")

# 5. Create commit
msg = subprocess.run(["git", "log", "--format=%B", "-n", "1", "HEAD"],
                     capture_output=True, text=True).stdout
commit = gh(f"{REPO}/git/commits", input_data={
    "message": msg.strip(),
    "tree": new_tree["sha"],
    "parents": [remote_sha],
    "author": {"name": "XuYiming", "email": "1378936642@qq.com"}
})
if not commit:
    sys.exit(1)
print(f"Commit: {commit['sha']}")

# 6. Update ref
result = gh(f"{REPO}/git/refs/heads/master",
            input_data={"sha": commit["sha"], "force": True}, method="PATCH")
if result:
    print("✅ 推送成功!")
else:
    print("推送失败")
    sys.exit(1)