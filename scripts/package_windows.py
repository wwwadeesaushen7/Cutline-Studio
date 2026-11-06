"""Create a source + built-website ZIP, deliberately excluding private workspace data."""
import argparse
from hashlib import sha256
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT.parent/'cutline-windows.zip')
    args=parser.parse_args()
    if not (ROOT/'frontend/dist/index.html').is_file():
        parser.error('Build the frontend with npm run build before packaging.')
    paths=[]
    for name in ['README.md','START-HERE.txt','WINDOWS-GUIDE.txt','1 - Setup.bat','2 - Open Cutline.bat','requirements.txt','requirements-dev.txt','requirements.lock.txt','.gitignore','.gitattributes','Dockerfile','.dockerignore','railway.json','frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/vite.config.js']:
        paths.append(ROOT/name)
    for directory in ['backend','scripts','tests']:
        paths.extend((ROOT/directory).glob('*.py'))
    paths.extend((ROOT/'scripts').glob('*.sh'))
    paths.append(ROOT/'scripts'/'windows-downloads.json')
    paths.extend((ROOT/'docs').glob('*.md'))
    paths.extend(path for path in (ROOT/'backend/models').iterdir() if path.is_file())
    for directory in ['frontend/src','frontend/public','frontend/dist','frontend/tests']:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file())
    output=args.output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            archive.write(path,Path('Cutline Studio')/path.relative_to(ROOT))
    checksum=sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{checksum}  {output.name}\n')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert all(not set(Path(p).parts)&{'.data','.venv','.git','node_modules','.cache','.tools','__pycache__'} for p in archive.namelist())
    print(f'Created {output} ({output.stat().st_size:,} bytes)')
    print(f'SHA256 {checksum}')


if __name__=='__main__':
    main()
