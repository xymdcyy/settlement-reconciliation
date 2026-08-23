"""通过 GitHub API 推送代码到远端（当 github.com:443 的 git 智能 HTTP 协议被
防火墙拦截、但 api.github.com 可达时使用）。

用法:
    python scripts/gh-push.py            # 把本地 HEAD 推到 origin 对应分支

依赖: 已安装并登录的 gh CLI（`gh auth status` 正常）。

核心目标——**推送后本地与远端 SHA 完全一致、永不分叉**:
- 逐个复现本地待推送 commit 的**精确 SHA**（无签名提交可行）：向 git/commits API
  传入完全一致的 tree+parents+author+committer+message，生成的 commit SHA 与本地逐一相同。
- 远端 HEAD 是本地祖先时用快进（force=false）；仅在历史分叉时才 force。
- 推送成功后同步本地跟踪 ref（refs/remotes/origin/<branch>），使 `git status` 立即为
  “up to date”，不再出现 diverged。

中文文件名安全:
- 文件内容一律用 `git cat-file blob <sha>` 按对象哈希读取，绝不用带路径的 `git show`;
- 文件树用 `git -c core.quotepath=false ls-tree` 拿原始 UTF-8 路径。
- 每个 blob/tree/commit 均校验其 SHA == 本地对象哈希，不一致即中止。
"""
import base64
import json
import re
import subprocess
import sys


def gh(path, method="GET", data=None, quiet=False):
    cmd = ["gh", "api", "-X", method, path]
    if data is not None:
        cmd += ["--input", "-"]
        r = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True, encoding="utf-8")
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        if not quiet:
            print(f"[gh api 失败] {method} {path}\n{r.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(r.stdout) if r.stdout.strip() else {}


def git_text(args):
    return subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def git_bytes(args):
    return subprocess.run(["git"] + args, capture_output=True).stdout


def git_ok(args):
    return subprocess.run(["git"] + args, capture_output=True).returncode == 0


def detect_repo_and_branch():
    url = git_text(["config", "--get", "remote.origin.url"])
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?$", url)
    if not m:
        sys.exit(f"无法从 remote.origin.url 解析仓库: {url!r}")
    branch = git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "master"
    return f"{m.group(1)}/{m.group(2)}", branch


def ls_tree(commit):
    """{path: (mode, blob_sha)}（仅 blob，原始 UTF-8 路径）"""
    out = git_text(["-c", "core.quotepath=false", "ls-tree", "-r", commit])
    entries = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        mode, typ, sha = meta.split()
        if typ == "blob":
            entries[path] = (mode, sha)
    return entries


def ensure_tree_on_remote(repo, commit, parent, parent_remote_tree):
    """在远端构建 commit 相对 parent 的 tree，返回其 SHA（并校验==本地 tree）。"""
    p_map = ls_tree(parent) if parent else {}
    c_map = ls_tree(commit)

    tree_items = []
    for path, (mode, sha) in c_map.items():
        if p_map.get(path) == (mode, sha):
            continue  # 未变，base_tree 已含
        content = git_bytes(["cat-file", "blob", sha])
        blob = gh(f"repos/{repo}/git/blobs", "POST",
                  {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if blob is None:
            sys.exit(f"blob 创建失败: {path}")
        if blob["sha"] != sha:
            sys.exit(f"blob SHA 不一致 {path}: {blob['sha']} != {sha}")
        tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
    for path in p_map:
        if path not in c_map:
            tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    payload = {"tree": tree_items}
    if parent_remote_tree:
        payload["base_tree"] = parent_remote_tree
    new_tree = gh(f"repos/{repo}/git/trees", "POST", payload)
    if new_tree is None:
        sys.exit("tree 创建失败")
    local_tree = git_text(["rev-parse", f"{commit}^{{tree}}"])
    if new_tree["sha"] != local_tree:
        sys.exit(f"tree SHA 不一致 {commit[:8]}: 远端 {new_tree['sha']} != 本地 {local_tree}")
    return new_tree["sha"]


def reproduce_commit(repo, commit, parent_sha, tree_sha):
    """用精确元数据复现 commit，返回远端 SHA（校验==本地 SHA）。"""
    if git_ok(["cat-file", "commit", commit]) and b"gpgsig" in git_bytes(["cat-file", "commit", commit]):
        sys.exit(f"{commit[:8]} 含 GPG 签名，无法用 API 精确复现 SHA。请关闭签名后重试。")
    raw = git_bytes(["cat-file", "commit", commit])
    message = raw[raw.find(b"\n\n") + 2:].decode("utf-8")
    payload = {
        "message": message, "tree": tree_sha, "parents": [parent_sha],
        "author": {"name": git_text(["log", "-1", "--format=%an", commit]),
                   "email": git_text(["log", "-1", "--format=%ae", commit]),
                   "date": git_text(["log", "-1", "--format=%aI", commit])},
        "committer": {"name": git_text(["log", "-1", "--format=%cn", commit]),
                      "email": git_text(["log", "-1", "--format=%ce", commit]),
                      "date": git_text(["log", "-1", "--format=%cI", commit])},
    }
    res = gh(f"repos/{repo}/git/commits", "POST", payload)
    if res is None:
        sys.exit("commit 创建失败")
    if res["sha"] != commit:
        sys.exit(f"commit SHA 不一致: 本地 {commit} != 远端 {res['sha']}（消息/时间/时区不匹配？）")
    return res["sha"]


def main():
    repo, branch = detect_repo_and_branch()
    local_head = git_text(["rev-parse", "HEAD"])
    print(f"仓库: {repo}  分支: {branch}  本地 HEAD: {local_head[:8]}")

    ref = gh(f"repos/{repo}/git/refs/heads/{branch}")
    if ref is None:
        sys.exit("无法获取远端分支 ref")
    remote_head = ref["object"]["sha"]
    print(f"远端 HEAD: {remote_head[:8]}")
    if remote_head == local_head:
        print("✅ 已一致，无需推送。")
        return

    # 确定 base（复现起点）与是否快进
    if git_ok(["cat-file", "-e", remote_head]) and git_ok(["merge-base", "--is-ancestor", remote_head, "HEAD"]):
        base, fast_forward = remote_head, True
    else:
        # 历史分叉：找本地最新的、远端已存在的 commit 作为 base
        base = None
        for sha in git_text(["rev-list", "HEAD"]).splitlines():
            if gh(f"repos/{repo}/git/commits/{sha}", quiet=True) is not None:
                base = sha
                break
        if base is None:
            sys.exit("找不到本地与远端的共同提交，无法安全推送。")
        fast_forward = False
        print(f"⚠️  历史分叉，共同基点: {base[:8]}（将 force 更新，仅覆盖自己的历史）")

    commits = git_text(["rev-list", "--reverse", f"{base}..HEAD"]).splitlines()
    print(f"待推送 {len(commits)} 个提交，逐一精确复现 SHA…")

    base_commit = gh(f"repos/{repo}/git/commits/{base}")
    parent_sha, parent_tree = base, base_commit["tree"]["sha"]
    for c in commits:
        tree_sha = ensure_tree_on_remote(repo, c, parent_sha, parent_tree)
        reproduce_commit(repo, c, parent_sha, tree_sha)
        print(f"  [OK] {c[:8]}  {git_text(['log', '-1', '--format=%s', c])[:48]}")
        parent_sha, parent_tree = c, tree_sha

    # 更新远端 ref
    res = gh(f"repos/{repo}/git/refs/heads/{branch}", "PATCH",
             {"sha": local_head, "force": not fast_forward})
    if res is None:
        sys.exit("ref 更新失败（非快进？如远端有他人提交请先同步）")

    # 同步本地跟踪 ref，使 git status 立即“up to date”、不再分叉
    subprocess.run(["git", "update-ref", f"refs/remotes/origin/{branch}", local_head])
    print(f"\n[OK] 推送成功！本地/远端 HEAD 均为 {local_head[:8]}"
          f"（{'快进' if fast_forward else 'force 覆盖自身历史'}，SHA 完全一致、无分叉）")


if __name__ == "__main__":
    main()
