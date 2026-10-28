"""Build a clean user package; no solver results, original PDFs or virtualenv."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parent.parent
out=root.parent/'output'
out.mkdir(exist_ok=True)
archive=out/'pecvd-fluent-mcp-2024R1.zip'
paths=[]
for name in ['README.md','pyproject.toml','.gitignore','local-config.example.json','01_Install.cmd','02_Check.cmd','Start_MCP.cmd']:
    paths.append(root/name)
for directory in ['pecvd_mcp','tests','docs','tools','examples']:
    for path in (root/directory).rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.log']:
            paths.append(path)
with ZipFile(archive,'w',ZIP_DEFLATED) as stream:
    for path in sorted(paths):
        content=path.read_bytes()
        if path.suffix=='.cmd':content=content.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
        stream.writestr('pecvd-fluent-mcp/'+path.relative_to(root).as_posix(),content)
with ZipFile(archive) as stream:
    assert stream.testzip() is None
    assert not any('/.venv/' in name or name.endswith(('.pdf','.cas.h5','.dat.h5')) for name in stream.namelist())
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
(out/'pecvd-fluent-mcp-2024R1.sha256').write_text(f'{checksum}  {archive.name}\n',encoding='ascii')
print(json.dumps({'file':str(archive),'files':len(paths),'bytes':archive.stat().st_size,'sha256':checksum},indent=2))
