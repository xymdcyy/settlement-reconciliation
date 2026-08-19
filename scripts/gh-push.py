"""通过 GitHub API 推送代码（git push 的 443 端口被防火墙拦截时使用）
用法: python scripts/gh-push.py
"""

import json
import subprocess
import sys
from pathlib import Path


def gh(*args, input_data=None, method="POST"):
    """调用 gh api 命令"""
    cmd = ["gh", "api", "-X", method] + list(args)
    if input_data:
        stdin = json.dumps(input_data)
    else:
        stdin = None
    r = subprocess.run(cmd, capture_output=True, text=True, input=stdin)
    if r.returncode != 0:
        print(f"gh api 错误: {r.stderr}")
        return None
    return json.loads(r.stdout)


def run(cmd):
    """运行 shell 命令，返回 stdout"""
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if r.returncode != 0:
        print(f"命令错误: {cmd}\n{r.stderr}")
        return None
    return r.stdout.strip()


def main():
    repo = "repos/xymdcyy/settlement-reconciliation"

    # 1. 获取远程 HEAD
    remote_ref = gh(f"{repo}/git/refs/heads/master", method="GET")
    if not remote_ref:
        print("无法获取远程分支")
        sys.exit(1)
    remote_commit_sha = remote_ref["object"]["sha"]
    print(f"远程 HEAD: {remote_commit_sha}")

    # 2. 获取远程 commit 的 tree
    remote_commit = gh(f"{repo}/git/commits/{remote_commit_sha}", method="GET")
    if not remote_commit:
        print("无法获取远程 commit")
        sys.exit(1)
    remote_base_tree = remote_commit["tree"]["sha"]
    print(f"远程 base tree: {remote_base_tree}")

    # 3. 获取本地相对于远程的变更文件列表
    diff_files = run(f"git diff --name-only {remote_commit_sha} HEAD")
    if not diff_files:
        print("没有变更")
        return
    files = [f for f in diff_files.split("\n") if f]
    print(f"变更文件 ({len(files)}): {files}")

    # 4. 为每个新增/修改的文件创建 blob
    new_blobs = []
    for file_path in files:
        if not Path(file_path).exists():
            continue
        content = Path(file_path).read_bytes()
        import base64
        content_b64 = base64.b64encode(content).decode()

        blob = gh(f"{repo}/git/blobs",
                  input_data={"content": content_b64, "encoding": "base64"})
        if blob:
            new_blobs.append((file_path, blob["sha"], "100644"))
            print(f"  blob 创建: {file_path} -> {blob['sha'][:8]}")

    # 5. 创建新的 tree
    tree_items = [{"path": p, "mode": m, "type": "blob", "sha": s}
                   for p, s, m in new_blobs]

    new_tree = gh(f"{repo}/git/trees",
                  input_data={"base_tree": remote_base_tree, "tree": tree_items})
    if not new_tree:
        print("无法创建 tree")
        sys.exit(1)
    new_tree_sha = new_tree["sha"]
    print(f"新 tree SHA: {new_tree_sha}")

    # 6. 获取 commit message
    msg = run("git log --format=%B -n 1 HEAD")
    author = run('git log --format="%an <%ae>" -n 1 HEAD')

    author_name = author.split("<")[0].strip() if author else "XuYiming"
    author_email = author.split("<")[1].rstrip(">") if author and "<" in author else "1378936642@qq.com"

    # 7. 创建新的 commit
    new_commit = gh(f"{repo}/git/commits",
                    input_data={
                        "message": msg,
                        "tree": new_tree_sha,
                        "parents": [remote_commit_sha],
                        "author": {"name": author_name, "email": author_email},
                    })
    if not new_commit:
        print("无法创建 commit")
        sys.exit(1)
    new_commit_sha = new_commit["sha"]
    print(f"新 commit SHA: {new_commit_sha}")

    # 8. 更新远程分支
    result = gh(f"{repo}/git/refs/heads/master",
                input_data={"sha": new_commit_sha, "force": True},
                method="PATCH")
    if result:
        print(f"\n✅ 推送成功!")
        print(f"   新 commit: {new_commit_sha[:8]}")
        print(f"   信息: {msg[:80].strip()}")
    else:
        print("推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()