#!/usr/bin/env python3
"""通过 GitHub API 推送完整的文件树到远程仓库

用法: python scripts/full_push.py
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

REPO = "repos/xymdcyy/settlement-reconciliation"


def gh(*args, stdin_data=None):
    """调用 gh api 命令，处理 GBK 编码问题"""
    cmd = ["gh", "api"] + list(args)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    input_bytes = stdin_data.encode("utf-8") if stdin_data else None
    stdout, stderr = proc.communicate(input=input_bytes)
    if proc.returncode != 0:
        print(f"gh error: {stderr.decode('utf-8', errors='replace')[:300]}")
        return None
    return json.loads(stdout.decode("utf-8"))


def main():
    repo_dir = "D:\\结算对账中心"

    # 1. 获取远程 HEAD
    r = gh(f"{REPO}/git/refs/heads/master")
    if not r:
        print("❌ 无法获取远程仓库状态")
        sys.exit(1)
    remote_sha = r["object"]["sha"]
    print(f"远程 HEAD: {remote_sha}")

    # 2. 获取所有文件的 git blob SHA
    result = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD"],
        capture_output=True, text=True, cwd=repo_dir,
    )
    tree_lines = result.stdout.strip().split("\n")
    print(f"本地文件数: {len(tree_lines)}")

    # 3. 上传所有文件为 blob（只上传二进制安全的 base64）
    tree_items = []
    for line in tree_lines:
        parts = line.split("\t")
        meta = parts[0].split()
        mode, obj_type, git_sha = meta[0], meta[1], meta[2]
        path = parts[1]

        # 读取文件内容
        with open(os.path.join(repo_dir, path), "rb") as f:
            content = f.read()

        b64 = base64.b64encode(content).decode("ascii")
        blob = gh(
            f"{REPO}/git/blobs",
            "--input", "-",
            stdin_data=json.dumps({"content": b64, "encoding": "base64"}),
        )
        if blob:
            tree_items.append({
                "path": path,
                "mode": mode,
                "type": "blob",
                "sha": blob["sha"],
            })
            print(f"  ✅ {path}")
        else:
            print(f"  ❌ {path}")

    print(f"\n已上传 {len(tree_items)} 个文件")

    # 4. 创建完整的 tree
    new_tree = gh(
        f"{REPO}/git/trees",
        "--input", "-",
        stdin_data=json.dumps({"tree": tree_items}),
    )
    if not new_tree:
        print("❌ 创建 tree 失败")
        sys.exit(1)
    new_tree_sha = new_tree["sha"]
    print(f"新 tree: {new_tree_sha}")

    # 5. 创建 commit
    msg = "sync: 同步本地完整文件树到远程\n\n完整推送项目所有文件，修复远程 tree 不完整的问题"
    commit = gh(
        f"{REPO}/git/commits",
        "--input", "-",
        stdin_data=json.dumps({
            "message": msg,
            "tree": new_tree_sha,
            "parents": [remote_sha],
            "author": {"name": "XuYiming", "email": "1378936642@qq.com"},
        }),
    )
    if not commit:
        print("❌ 创建 commit 失败")
        sys.exit(1)
    commit_sha = commit["sha"]
    print(f"新 commit: {commit_sha}")

    # 6. 更新 ref
    result = gh(
        f"{REPO}/git/refs/heads/master",
        "-X", "PATCH",
        "--input", "-",
        stdin_data=json.dumps({"sha": commit_sha, "force": True}),
    )
    if result:
        print("✅ 推送成功！")
        print(f"   https://github.com/xymdcyy/settlement-reconciliation/commit/{commit_sha}")
    else:
        print("❌ 推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()