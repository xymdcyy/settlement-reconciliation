import json, subprocess, hashlib, zlib, os, sys, platform
from datetime import datetime, timezone

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

# 从 API 获取远程 commit 详细信息
result = subprocess.run(
    ['gh', 'api', 'repos/xymdcyy/settlement-reconciliation/git/commits/7704475dada9e817d736c5973fd9b31758f9d81a'],
    capture_output=True, env=env
)
stdout = result.stdout.decode('utf-8')
commit = json.loads(stdout)

tree = commit['tree']['sha']
parents = [p['sha'] for p in commit['parents']]
author = commit['author']
committer = commit.get('committer', author)
message = commit['message']  # API 返回的 message 不含末尾 \n

def to_git_timestamp(d):
    """ISO 8601 -> 'unix_timestamp +0000'"""
    dt = datetime.strptime(d['date'], '%Y-%m-%dT%H:%M:%SZ')
    dt = dt.replace(tzinfo=timezone.utc)
    return f'{int(dt.timestamp())} +0000'

author_line = f'{author["name"]} <{author["email"]}> {to_git_timestamp(author)}'
committer_line = f'{committer["name"]} <{committer["email"]}> {to_git_timestamp(committer)}'

# 构建 git commit 原始内容
# 注意: API 创建的 commit 在 message 末尾没有 \n
content = f'tree {tree}\n'
content += ''.join(f'parent {p}\n' for p in parents)
content += f'author {author_line}\n'
content += f'committer {committer_line}\n'
content += f'\n{message}'  # 不加末尾 \n

raw = f'commit {len(content.encode())}\0{content}'.encode()
sha = hashlib.sha1(raw).hexdigest()
print(f'Expected SHA: 7704475dada9e817d736c5973fd9b31758f9d81a')
print(f'Computed SHA: {sha} (no trailing \\n)')

if sha == '7704475dada9e817d736c5973fd9b31758f9d81a':
    obj_dir = os.path.join(r'D:\结算对账中心\.git\objects', sha[:2])
    obj_file = os.path.join(obj_dir, sha[2:])
    os.makedirs(obj_dir, exist_ok=True)
    compressed = zlib.compress(raw)
    with open(obj_file, 'wb') as f:
        f.write(compressed)
    print(f'Written to: {obj_file}')
    # 更新本地 ref
    subprocess.run(['git', 'update-ref', 'refs/heads/master', sha], cwd=r'D:\结算对账中心')
    print(f'本地 ref 已更新到 {sha}')
    sys.exit(0)
else:
    # 尝试有末尾 \n 的情况
    content2 = f'tree {tree}\n'
    content2 += ''.join(f'parent {p}\n' for p in parents)
    content2 += f'author {author_line}\n'
    content2 += f'committer {committer_line}\n'
    content2 += f'\n{message}\n'
    raw2 = f'commit {len(content2.encode())}\0{content2}'.encode()
    sha2 = hashlib.sha1(raw2).hexdigest()
    print(f'Computed SHA: {sha2} (with trailing \\n)')
    if sha2 == '7704475dada9e817d736c5973fd9b31758f9d81a':
        obj_dir = os.path.join(r'D:\结算对账中心\.git\objects', sha2[:2])
        obj_file = os.path.join(obj_dir, sha2[2:])
        os.makedirs(obj_dir, exist_ok=True)
        compressed = zlib.compress(raw2)
        with open(obj_file, 'wb') as f:
            f.write(compressed)
        print(f'Written to: {obj_file}')
        subprocess.run(['git', 'update-ref', 'refs/heads/master', sha2], cwd=r'D:\结算对账中心')
        print(f'本地 ref 已更新到 {sha2}')
        sys.exit(0)
    else:
        print('=== 两种格式都不匹配 ===')
        print(f'Message length: {len(message)}')
        print(f'Message repr: {repr(message)}')
        sys.exit(1)