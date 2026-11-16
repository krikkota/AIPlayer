"""Compile a per-user Windows installer. Does not launch or test the application."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tomllib

root=Path(__file__).resolve().parents[1]
if sys.platform!='win32':
    raise SystemExit('Compile the Windows installer on a Windows build machine.')
version=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
app=root/'outputs/AIPlayer/AIPlayer.exe'
data=app.read_bytes()
if data[:2]!=b'MZ':raise RuntimeError('The payload is not a Windows executable')
pe=struct.unpack_from('<I',data,0x3c)[0]
if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x8664:
    raise RuntimeError('The installer requires a real Windows x64 application')
paths=[os.getenv('ISCC_PATH',''),shutil.which('ISCC.exe') or '']
for prefix in ('ProgramFiles','ProgramFiles(x86)'):
    for major in (7,6):paths.append(str(Path(os.getenv(prefix,''))/f'Inno Setup {major}/ISCC.exe'))
compiler=next((Path(p) for p in paths if p and Path(p).is_file()),None)
if compiler is None:raise SystemExit('Inno Setup compiler was not found. Set ISCC_PATH.')
subprocess.run([str(compiler),'/Qp',f'/DAppVersion={version}',f'/DProjectRoot={root}',
                str(root/'packaging/windows.iss')],cwd=root,check=True)
target=root/f'outputs/AIPlayer-{version}-Windows-x64-Setup.exe'
with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
if target.stat().st_size<1_000_000:raise RuntimeError('Installer payload is unexpectedly small')
metadata=dict(version=version,file=target.name,bytes=target.stat().st_size,sha256=sha,
              platform='Windows',architecture='x64',installer='Inno Setup',per_user=True,
              signed=False,runtime_tested=False,models_bundled=False)
(root/'outputs/windows-installer.json').write_text(json.dumps(metadata,indent=2)+'\n')
with (root/'outputs/SHA256SUMS.txt').open('a') as stream:stream.write(f'{sha}  {target.name}\n')
print(f'INSTALLER_READY {target.name} {target.stat().st_size} bytes SHA256={sha}')
