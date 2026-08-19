"""通过 Git Data API 推送本地 commit 到远程"""
import json, subprocess, sys, base64, os, tempfile

COMMIT_SHA = "ff5b00727ca718d6779a2b4a3bbdb4fd61707570"
REPO = "repos/xymdcyy/settlement-reconciliation"


def gh(cmd, input_data=None):
    """Run gh api command"""
    parts = ["gh", "api", f"{REPO}/git/{cmd}"]
    if input_data:
        result = subprocess.run(
            parts,
            input=json.dumps(input_data).encode(),
            capture_output=True,
        )
    else:
        result = subprocess.run(parts, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        if "already_exists" in err or "Object does not exist" not in err:
            pass  # 某些错误可以忽略
    return result.stdout.decode("utf-8", errors="replace")


def main():
    # 获取当前 commit 的信息
    result = subprocess.run(
        ["git", "cat-file", "-p", COMMIT_SHA],
        capture_output=True, cwd=r"D:\结算对账中心"
    )
    commit_info = result.stdout.decode()

    # 解析 tree sha
    tree_sha = None
    for line in commit_info.splitlines():
        if line.startswith("tree "):
            tree_sha = line.split()[1]
            break
    print(f"Tree SHA: {tree_sha}")

    # 获取 tree 内容
    result = subprocess.run(
        ["git", "ls-tree", "-r", tree_sha],
        capture_output=True, cwd=r"D:\结算对账中心"
    )
    tree_entries = result.stdout.decode().strip().splitlines()
    print(f"Tree entries: {len(tree_entries)}")

    # 检查远程已有的 blob（通过已有 tree）
    # 直接创建新 tree 需要所有 blob 都在远程
    # 上传所有 blob 到远程
    blobs_map = {}
    for i, entry in enumerate(tree_entries):
        parts = entry.split()
        mode, obj_type, obj_sha, path = parts[0], parts[1], parts[2], " ".join(parts[3:])
        if obj_type == "blob":
            blobs_map[path] = obj_sha

    existing = 0
    uploaded = 0
    for path, sha in blobs_map.items():
        try:
            # 检查是否已存在
            r = subprocess.run(
                ["gh", "api", f"{REPO}/git/blobs/{sha}", "--jq", ".sha"],
                capture_output=True, timeout=10
            )
            if r.returncode == 0:
                existing += 1
                continue
        except:
            pass

        # 上传 blob
        result = subprocess.run(
            ["git", "cat-file", "-p", sha],
            capture_output=True, cwd=r"D:\结算对账中心"
        )
        content = result.stdout

        # 检测是否为二进制
        is_binary = False
        try:
            content.decode("utf-8")
        except:
            is_binary = True

        payload = {
            "content": base64.b64encode(content).decode() if is_binary else content.decode("utf-8", errors="replace"),
            "encoding": "base64" if is_binary else "utf-8",
        }

        r = subprocess.run(
            ["gh", "api", f"{REPO}/git/blobs", "--input", "-", "--jq", ".sha"],
            input=json.dumps(payload).encode(),
            capture_output=True, timeout=30
        )
        uploaded += 1
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(tree_entries)} (existing={existing}, uploaded={uploaded})")

    print(f"Blobs: {existing} existing, {uploaded} uploaded")

    # 创建新 tree（使用远程 tree 作为 base）
    # 获取父 commit 的 tree
    result = subprocess.run(
        ["gh", "api", f"{REPO}/git/commits/7704475dada9e817d736c5973fd9b31758f9d81a", "--jq", ".tree.sha"],
        capture_output=True
    )
    base_tree = result.stdout.decode().strip()
    print(f"Base tree: {base_tree}")

    # 构建 tree 数据
    tree_data = []
    for entry in tree_entries:
        parts = entry.split()
        mode, obj_type, obj_sha, path = parts[0], parts[1], parts[2], " ".join(parts[3:])
        tree_data.append({
            "path": path,
            "mode": mode,
            "type": obj_type,
            "sha": obj_sha,
        })

    # 分块创建 tree（避免 payload 太大）
    # 先创建 subtree
    print(f"Creating tree with {len(tree_data)} entries...")
    result = subprocess.run(
        ["gh", "api", f"{REPO}/git/trees", "--input", "-", "--jq", ".sha"],
        input=json.dumps({"tree": tree_data}).encode(),
        capture_output=True, timeout=60
    )
    if result.returncode != 0:
        print(f"Tree creation failed: {result.stderr.decode()}")
        sys.exit(1)

    new_tree_sha = result.stdout.decode().strip()
    print(f"New tree: {new_tree_sha}")

    # 创建 commit
    commit_payload = {
        "message": "feat: 前端上传页面 + 客户列表/上传历史 API\n\n- Vue 3 + Element Plus 前端项目初始化\n- 上传页面：拖拽/点击上传，进度条，导入统计，上传历史\n- 比对工作台：客户/期间选择，统计摘要，左右对照表格，手动纠正\n- 客户列表 API（GET /api/customers）\n- 上传历史模型 + API（GET /api/upload/history）\n- 种子数据脚本（scripts/seed.py）\n- 全部 46 个测试通过，前端构建通过",
        "tree": new_tree_sha,
        "parents": ["7704475dada9e817d736c5973fd9b31758f9d81a"],
        "author": {
            "name": "XuYiming",
            "email": "1378936642@qq.com",
            "date": "2026-08-19T20:17:51+08:00",
        },
        "committer": {
            "name": "XuYiming",
            "email": "1378936642@qq.com",
            "date": "2026-08-19T20:17:51+08:00",
        },
    }

    result = subprocess.run(
        ["gh", "api", f"{REPO}/git/commits", "--input", "-", "--jq", ".sha"],
        input=json.dumps(commit_payload).encode(),
        capture_output=True, timeout=30
    )
    if result.returncode != 0:
        print(f"Commit creation failed: {result.stderr.decode()}")
        sys.exit(1)

    remote_sha = result.stdout.decode().strip()
    print(f"Remote commit: {remote_sha}")

    # 更新 ref
    result = subprocess.run(
        ["gh", "api", f"{REPO}/git/refs/heads/master", "-X", "PATCH", "--input", "-"],
        input=json.dumps({"sha": remote_sha, "force": True}).encode(),
        capture_output=True, timeout=30
    )
    if result.returncode != 0:
        print(f"Ref update failed: {result.stderr.decode()}")
        sys.exit(1)

    print(f"Ref updated to {remote_sha}")
    print(f"Local SHA: {COMMIT_SHA}")
    print(f"Remote SHA: {remote_sha}")
    print("Note: 远程 SHA 和本地 SHA 不同，因为 tree 通过 API 重建")


if __name__ == "__main__":
    main()