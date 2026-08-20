"""通过 GitHub API 推送代码到远端（当 github.com:443 的 git 智能 HTTP 协议被
防火墙拦截、但 api.github.com 可达时使用）。

用法:
    python scripts/gh-push.py                 # 推送当前 HEAD 到 origin 对应分支
    python scripts/gh-push.py -m "提交信息"    # 覆盖提交信息

依赖: 已安装并登录的 gh CLI（`gh auth status` 正常）。

设计要点（吸取踩坑教训）:
- **中文文件名安全**: 文件内容一律用 `git cat-file blob <sha>` 按对象哈希读取，
  绝不用带路径的 `git show <sha>:<path>`（git 会对非 ASCII 路径加引号+八进制转义，
  导致取到空内容、并在远端建出字面引号命名的空垃圾文件）；路径仅用于 tree 结构，
  且统一用 `-c core.quotepath=false` 拿原始 UTF-8。
- **基于内容比对**: 直接对比本地 HEAD 与远端 HEAD 的文件树（blob 哈希），
  计算增/改/删。API 推送产生的远端 commit SHA 与本地不同、且不在本地历史中，
  因此不能用 `rev-list 远端..HEAD`；基于内容比对可反复稳定运行。
- **完整性校验**: 每个上传 blob 校验其 SHA == 本地 git 对象哈希；推送后再校验
  远端新 tree.sha == 本地 `git rev-parse HEAD^{tree}`（内容寻址，相等即逐字节一致）。
- **不改写历史**: ref 用 `force:false` 快进更新；非快进则拒绝并提示。
"""
import argparse
import base64
import json
import re
import subprocess
import sys


def gh(path, method="GET", data=None):
    """调用 gh api；data 非空时作为 JSON body 从 stdin 传入。"""
    cmd = ["gh", "api", "-X", method, path]
    if data is not None:
        cmd += ["--input", "-"]
        r = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True, encoding="utf-8")
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"[gh api 失败] {method} {path}\n{r.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(r.stdout) if r.stdout.strip() else {}


def git_text(args):
    return subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8").stdout


def git_bytes(args):
    return subprocess.run(["git"] + args, capture_output=True).stdout


def detect_repo_and_branch():
    """从本地 git 配置推断 owner/repo 与分支。"""
    url = git_text(["config", "--get", "remote.origin.url"]).strip()
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?$", url)
    if not m:
        sys.exit(f"无法从 remote.origin.url 解析仓库: {url!r}")
    owner, repo = m.group(1), m.group(2)
    branch = git_text(["rev-parse", "--abbrev-ref", "HEAD"]).strip() or "master"
    return owner, repo, branch


def local_tree_entries():
    """本地 HEAD 的全部文件: {path: blob_sha}（原始 UTF-8 路径）。"""
    out = git_text(["-c", "core.quotepath=false", "ls-tree", "-r", "HEAD"])
    entries = {}
    for line in out.splitlines():
        # 格式: "<mode> <type> <sha>\t<path>"
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            entries[path] = parts[2]
    return entries


def remote_tree_entries(repo, tree_sha):
    """远端 tree 的全部 blob: {path: sha}。"""
    data = gh(f"repos/{repo}/git/trees/{tree_sha}?recursive=1")
    if data is None:
        sys.exit("无法获取远端 tree")
    if data.get("truncated"):
        print("⚠️  远端 tree 过大被截断，删除检测可能不完整。", file=sys.stderr)
    return {e["path"]: e["sha"] for e in data.get("tree", []) if e["type"] == "blob"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", help="覆盖提交信息（默认用本地 HEAD 的提交信息）")
    args = ap.parse_args()

    owner, repo_name, branch = detect_repo_and_branch()
    repo = f"{owner}/{repo_name}"
    print(f"仓库: {repo}  分支: {branch}")

    # 1) 远端 HEAD 及其 tree
    ref = gh(f"repos/{repo}/git/refs/heads/{branch}")
    if ref is None:
        sys.exit("无法获取远端分支 ref（分支不存在？）")
    remote_head = ref["object"]["sha"]
    remote_commit = gh(f"repos/{repo}/git/commits/{remote_head}")
    remote_base_tree = remote_commit["tree"]["sha"]
    print(f"远端 HEAD: {remote_head[:8]}  tree: {remote_base_tree[:8]}")

    # 2) 本地 vs 远端，基于内容比对
    local = local_tree_entries()
    remote = remote_tree_entries(repo, remote_base_tree)

    changed = [(p, sha) for p, sha in local.items() if remote.get(p) != sha]
    deleted = [p for p in remote if p not in local]

    if not changed and not deleted:
        print("✅ 远端已与本地一致，无需推送。")
        return
    print(f"新增/修改 {len(changed)} 个文件，删除 {len(deleted)} 个文件")

    # 3) 上传 blob（内容按对象哈希读取，避免中文路径问题）+ 校验
    tree_items = []
    for path, sha in changed:
        content = git_bytes(["cat-file", "blob", sha])
        blob = gh(f"repos/{repo}/git/blobs", method="POST",
                  data={"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if blob is None:
            sys.exit(f"blob 创建失败: {path}")
        if blob["sha"] != sha:
            sys.exit(f"blob SHA 不一致 {path}: 远端 {blob['sha']} != 本地 {sha}")
        print(f"  ✓ {path}  ({len(content)}B)")
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
    for path in deleted:
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
        print(f"  ✗ 删除 {path}")

    # 4) 建 tree + commit
    new_tree = gh(f"repos/{repo}/git/trees", method="POST",
                  data={"base_tree": remote_base_tree, "tree": tree_items})
    if new_tree is None:
        sys.exit("tree 创建失败")

    msg = args.message or git_text(["log", "--format=%B", "-n", "1", "HEAD"]).rstrip("\n")
    an = git_text(["log", "--format=%an", "-n", "1", "HEAD"]).strip() or "XuYiming"
    ae = git_text(["log", "--format=%ae", "-n", "1", "HEAD"]).strip() or "noreply@github.com"
    new_commit = gh(f"repos/{repo}/git/commits", method="POST",
                    data={"message": msg, "tree": new_tree["sha"], "parents": [remote_head],
                          "author": {"name": an, "email": ae}})
    if new_commit is None:
        sys.exit("commit 创建失败")

    # 5) 快进更新 ref（不改写历史）
    result = gh(f"repos/{repo}/git/refs/heads/{branch}", method="PATCH",
                data={"sha": new_commit["sha"], "force": False})
    if result is None:
        sys.exit("ref 更新失败（可能非快进；如远端有他人提交，请先同步）")

    # 6) 最终校验：远端 tree 必须与本地 HEAD tree 逐字节一致
    local_head_tree = git_text(["rev-parse", "HEAD^{tree}"]).strip()
    if new_tree["sha"] == local_head_tree:
        print(f"\n✅ 推送成功！远端 {branch} -> {new_commit['sha'][:8]}（tree 与本地完全一致）")
    else:
        print(f"\n⚠️  推送完成但 tree 不一致：远端 {new_tree['sha'][:8]} != 本地 {local_head_tree[:8]}，请检查。",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
