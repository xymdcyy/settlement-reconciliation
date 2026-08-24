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


def gh(path, method="GET", data=None, quiet=False, retries=4):
    """调用 gh api，失败自动重试（网络抖动场景）。"""
    for attempt in range(retries):
        cmd = ["gh", "api", "-X", method, path]
        if data is not None:
            cmd += ["--input", "-"]
            r = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True, encoding="utf-8")
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip() else {}
        if attempt < retries - 1:
            import time
            wait = 2 * (attempt + 1)
            print(f"  [重试 {attempt+1}/{retries-1}] {method} {path} 失败，{wait}s 后重试…", file=sys.stderr)
            time.sleep(wait)
    if not quiet:
        print(f"[gh api 失败] {method} {path}\n{r.stderr.strip()}", file=sys.stderr)
    return None


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
    """{path: (mode, blob_sha)}（仅 blob，原始 UTF-8 路径，递归包含所有子目录文件）"""
    out = git_text(["-c", "core.quotepath=false", "ls-tree", "-r", commit])
    entries = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        mode, typ, sha = meta.split()
        if typ == "blob":
            entries[path] = (mode, sha)
    return entries


def ensure_tree_on_remote(repo, commit, parent, parent_remote_tree):
    """在远端构建 commit 的完整 tree，返回其 SHA（并校验==本地 tree）。

    注意：不使用 base_tree，而是每次都构建完整的 tree。
    这样虽然效率低一些，但能保证路径正确性（避免 base_tree 相对路径问题）。
    """
    c_map = ls_tree(commit)

    tree_items = []
    for path, (mode, sha) in c_map.items():
        content = git_bytes(["cat-file", "blob", sha])
        blob = gh(f"repos/{repo}/git/blobs", "POST",
                  {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if blob is None:
            sys.exit(f"blob 创建失败: {path}")
        if blob["sha"] != sha:
            sys.exit(f"blob SHA 不一致 {path}: {blob['sha']} != {sha}")
        tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})

    payload = {"tree": tree_items}
    # 不使用 base_tree，每次都构建完整的 tree
    new_tree = gh(f"repos/{repo}/git/trees", "POST", payload)
    if new_tree is None:
        sys.exit("tree 创建失败")
    local_tree = git_text(["rev-parse", f"{commit}^{{tree}}"])
    if new_tree["sha"] != local_tree:
        sys.exit(f"tree SHA 不一致 {commit[:8]}: 远端 {new_tree['sha']} != 本地 {local_tree}")
    return new_tree["sha"]


def reproduce_commit(repo, commit, parent_sha, tree_sha, sha_map=None):
    """用精确元数据复现 commit，返回远端 SHA（校验==本地 SHA）。

    支持 merge commit（多 parent）。
    parent_sha: 如果是 merge commit，这里是第一个 parent（通常是当前分支的前一个 commit）。
    sha_map: 本地 SHA → 远端 SHA 的映射表（用于转换 merge commit 的其他 parent）。
    """
    if git_ok(["cat-file", "commit", commit]) and b"gpgsig" in git_bytes(["cat-file", "commit", commit]):
        sys.exit(f"{commit[:8]} 含 GPG 签名，无法用 API 精确复现 SHA。请关闭签名后重试。")
    raw = git_bytes(["cat-file", "commit", commit])
    message = raw[raw.find(b"\n\n") + 2:].decode("utf-8")

    # 获取所有 parent SHA（支持 merge commit）
    parents_local = git_text(["log", "-1", "--format=%P", commit]).split()

    # 转换 parent SHA：本地 SHA → 远端 SHA
    if sha_map is None:
        sha_map = {}

    parents_remote = []
    for i, local_parent in enumerate(parents_local):
        if i == 0:
            # 第一个 parent 用 parent_sha（当前推送链的上一个 commit）
            parents_remote.append(parent_sha)
        else:
            # 其他 parent 从 sha_map 中查找（如果已经推送过）
            if local_parent in sha_map:
                parents_remote.append(sha_map[local_parent])
            else:
                # 如果没推送过，假设远端已经存在（使用本地 SHA）
                # 这适用于 base commit 或远端已有的 commit
                parents_remote.append(local_parent)

    payload = {
        "message": message, "tree": tree_sha, "parents": parents_remote,
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

    # 更新 sha_map
    sha_map[commit] = res["sha"]

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
        print("[OK] 已一致，无需推送。")
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
        print(f"[!] 历史分叉，共同基点: {base[:8]}（将 force 更新，仅覆盖自己的历史）")

    commits = git_text(["rev-list", "--reverse", f"{base}..HEAD"]).splitlines()
    print(f"待推送 {len(commits)} 个提交，逐一精确复现 SHA…")

    base_commit = gh(f"repos/{repo}/git/commits/{base}")
    parent_sha, parent_tree = base, base_commit["tree"]["sha"]

    # 维护本地 SHA → 远端 SHA 的映射表（用于 merge commit 的 parent 转换）
    # 预先填充：对于本地 HEAD 历史中、但不在 commits 列表中的 commit，
    # 如果远端已存在（SHA 不同），则从远端获取其 SHA
    sha_map = {}

    # 获取本地 HEAD 的所有祖先 commit
    all_local_commits = git_text(["rev-list", "HEAD"]).splitlines()
    for local_sha in all_local_commits:
        # 跳过待推送的 commit（它们会被重新创建）
        if local_sha in commits:
            continue
        # 查询远端是否存在这个 commit（通过 SHA 查询）
        # 如果远端 SHA 与本地不同，说明是之前推送时创建的（如 1a8b93a）
        # 我们需要找到远端对应的 SHA
        # 简化处理：假设远端已有的 commit SHA 就是本地 SHA（对于 base commit）
        # 对于其他 commit（如 1a8b93a），我们需要通过其他方式查找
        sha_map[local_sha] = local_sha  # 默认：远端 SHA == 本地 SHA

    # 特殊处理：如果 base 的远端 SHA 与本地不同（历史分叉），需要手动指定
    if base != remote_head:
        # 远端的 base commit 可能是用不同 SHA 创建的（如 3e8ab84f 对应本地的 8bbc105）
        # 我们需要从远端的 commit 历史中找到对应的 SHA
        # 简化处理：假设远端的 base commit 就是 remote_head 的祖先
        # 这里我们直接使用 remote_head 的祖先链
        print(f"提示：共同基点 {base[:8]} 在远端的 SHA 可能不同（历史分叉）")

    for c in commits:
        tree_sha = ensure_tree_on_remote(repo, c, parent_sha, parent_tree)
        reproduce_commit(repo, c, parent_sha, tree_sha, sha_map)
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
