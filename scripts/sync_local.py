"""Inject remote commit object into local .git/objects"""
import json, subprocess, hashlib, zlib, os, sys
from datetime import datetime, timezone

REMOTE_SHA = "1775f43857bd970b4480a810d81890195bd5755f"
REPO = "repos/xymdcyy/settlement-reconciliation"

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

result = subprocess.run(
    ['gh', 'api', f'{REPO}/git/commits/{REMOTE_SHA}', '--jq', '{tree: .tree.sha, parent: .parents[0].sha, author: .author, committer: .committer, message: .message}'],
    capture_output=True, env=env
)
data = json.loads(result.stdout.decode('utf-8'))

tree = data['tree']
parent = data['parent']
author = data['committer']  # committer and author are same
message = data['message']

def to_ts(d, offset="+0000"):
    dt = datetime.strptime(d['date'], '%Y-%m-%dT%H:%M:%SZ')
    dt = dt.replace(tzinfo=timezone.utc)
    return f'{int(dt.timestamp())} {offset}'

# offset=+0800, no trailing newline (matches previous debug output)
auth_line = f'{author["name"]} <{author["email"]}> {to_ts(author, "+0800")}'
comm_line = f'{author["name"]} <{author["email"]}> {to_ts(author, "+0800")}'

content = f'tree {tree}\n'
content += f'parent {parent}\n'
content += f'author {auth_line}\n'
content += f'committer {comm_line}\n'
content += f'\n{message}'

raw = f'commit {len(content.encode())}\0{content}'.encode()
sha = hashlib.sha1(raw).hexdigest()
assert sha == REMOTE_SHA, f"SHA mismatch: {sha}"

obj_dir = os.path.join(r'D:\结算对账中心\.git\objects', sha[:2])
obj_file = os.path.join(obj_dir, sha[2:])
os.makedirs(obj_dir, exist_ok=True)
if os.path.isfile(obj_file):
    os.remove(obj_file)
compressed = zlib.compress(raw)
with open(obj_file, 'wb') as f:
    f.write(compressed)
print(f"Written to: {obj_file}")

subprocess.run(['git', 'update-ref', 'refs/heads/master', sha], cwd=r'D:\结算对账中心')
print(f"Local ref updated to {sha}")

# Verify
r = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, cwd=r'D:\结算对账中心')
print(f"HEAD: {r.stdout.decode().strip()}")
r = subprocess.run(['gh', 'api', f'{REPO}/git/refs/heads/master', '--jq', '.object.sha'], capture_output=True, env=env)
print(f"Remote: {r.stdout.decode().strip()}")