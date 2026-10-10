"""Build a separate submission using an allowlist; never change source datasets.

Run from the project root. Existing submission outputs are never overwritten.
Only contact addresses inside copied request user-agent metadata are redacted.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_submission_manifest import verify

EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_response(value):
    # Same canonical encoding as src.download_dataset.json_bytes.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def sanitize_metadata(raw):
    obj = json.loads(raw)
    fields = []
    def walk(value, prefix=''):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'response':
                    continue  # Original source response is immutable, including in copies.
                if key == 'user_agent' and isinstance(child, str) and EMAIL.search(child):
                    value[key] = EMAIL.sub('[CONTACT REDACTED]', child)
                    fields.append(prefix + '/' + key)
                else:
                    walk(child, prefix + '/' + key)
        elif isinstance(value, list):
            for index, child in enumerate(value): walk(child, prefix+'/'+str(index))
    walk(obj)
    if not fields:
        return raw, []
    result = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')
    if 'response' in obj:
        original = json.loads(raw)
        assert obj['response'] == original['response']
        assert obj['response_sha256'] == original['response_sha256']
        assert digest(canonical_response(obj['response'])) == obj['response_sha256']
    return result, fields


def selected_files():
    files = [ROOT / name for name in ['README.md','SUBMISSION_README.md','.gitignore','.env.example','requirements.txt','requirements-eda.txt','.github/agents/AGENTS.md']]
    for directory, pattern in [('src','*.py'),('scripts','*.py'),('tests','*.py'),('notebooks','*.ipynb'),('sql','*.sql'),('reports','*.md'),('reports','*.dbml'),('reports','*.png'),('reports/figures','*.png'),('reports/sql_results','*.csv'),('data/cleaned','*.csv'),('data/processed','*.csv'),('data/processed','*.json')]:
        files.extend((ROOT/directory).glob(pattern))
    for name in ['FoodLens_Final_Report.docx','FoodLens_Final_Report.pdf']:
        if (ROOT/'reports'/name).is_file(): files.append(ROOT/'reports'/name)
    files.extend(ROOT/'data/raw'/name for name in ['food_products_raw.json','food_products_extracted.csv'])
    for directory in (ROOT/'data/raw/extractions').iterdir():
        if not directory.is_dir(): continue
        files.extend(directory/name for name in ['checkpoint.json','manifest.json','barcode_issues.json'])
        files.extend((directory/'pages').glob('page_*.json'))
    result = sorted(set(files))
    if any(not p.is_file() or p.is_symlink() for p in result):
        raise ValueError('Missing or symbolic-link submission input')
    return result


def scan(root):
    # Never emit matched values. Test fixtures deliberately contain synthetic URLs.
    forbidden = {'.env','.venv','__pycache__','backups','.git','tmp','temp','.ipynb_checkpoints'}
    problems = []
    patterns = [r'\b(?:npg_|ghp_|github_pat_)[A-Za-z0-9_]{16,}', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'postgres(?:ql)?://[^\s\"\x27]+\.neon\.tech', r'\bsk-[A-Za-z0-9_-]{24,}']
    for p in root.rglob('*'):
        if not p.is_file(): continue
        name = p.relative_to(root).as_posix()
        if forbidden.intersection(p.relative_to(root).parts) or (p.name.startswith('.env') and p.name!='.env.example') or p.suffix in {'.pyc','.pem','.key','.p12','.pfx','.tmp'}:
            problems.append((name, 'forbidden path'))
        raw = p.read_bytes()
        if p.suffix in {'.png','.docx','.pdf'}: continue
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8',errors='replace')
        if any(re.search(pattern,text) for pattern in patterns): problems.append((name,'credential pattern'))
        for address in EMAIL.findall(text):
            if name == 'tests/test_download_dataset.py' and address == 'student' + '@' + 'university.edu':
                continue  # Existing mocked User-Agent fixture, not a real contact.
            if not address.lower().endswith(('@example.com','@example.invalid','@example.org','@example.test')):
                problems.append((name,'non-placeholder contact'))
        if re.search(r'[A-Za-z]:[\\/](?:Users|Github)[\\/]',text): problems.append((name,'local absolute path'))
    # Compare against local URL and password when present, without displaying either.
    env = ROOT/'.env'
    if env.exists():
        from urllib.parse import urlsplit, unquote
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if line.strip().startswith('DATABASE_URL='):
                value=line.split('=',1)[1].strip().strip('\"\x27')
                password=unquote(urlsplit(value).password or '')
                needles=[v.encode() for v in [value,password] if len(v)>=8]
                for p in root.rglob('*'):
                    if p.is_file() and any(n in p.read_bytes() for n in needles):
                        problems.append((p.relative_to(root).as_posix(),'local credential match'))
    if problems: raise ValueError('Submission privacy scan failed (values suppressed): '+repr(problems))
    print('PASS: forbidden paths, credential patterns, local credential matches, contacts and local path scan.')


def main():
    destination = ROOT/'submission/FoodLens'
    archive = ROOT/'submission/FoodLens_Submission.zip'
    if destination.exists() or archive.exists():
        raise SystemExit('STOP: submission folder or ZIP exists; move previous outputs aside before rebuilding.')
    files=selected_files()
    destination.mkdir(parents=True)
    redactions=[]
    for source in files:
        relative=source.relative_to(ROOT)
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        raw=source.read_bytes()
        if relative.as_posix().startswith('data/raw/extractions/') and source.suffix=='.json':
            raw,fields=sanitize_metadata(raw)
            if fields: redactions.append({'path':relative.as_posix(),'fields':fields})
        target.write_bytes(raw)
    (destination/'reports/submission_redactions.json').write_text(json.dumps(redactions,indent=2)+'\n',encoding='utf-8')
    scan(destination)
    rows=[]
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            raw=path.read_bytes()
            rows.append(dict(path=path.relative_to(destination).as_posix(),bytes=len(raw),sha256=digest(raw)))
    manifest=dict(project='FoodLens',format_version=1,files=rows)
    (destination/'SUBMISSION_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    verify(destination)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(destination.rglob('*')):
            if path.is_file(): z.write(path,'FoodLens/'+path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert len(names)==len(set(names))==len(rows)+1
        for name in names:
            assert name.startswith('FoodLens/') and '\\' not in name and '..' not in Path(name).parts
            assert z.read(name)==(destination/name.removeprefix('FoodLens/')).read_bytes()
    archive.with_suffix('.zip.sha256').write_text(digest(archive.read_bytes())+'  '+archive.name+'\n',encoding='ascii')
    print(f'PASS: ZIP integrity, {len(rows)+1} files, relative paths and byte-for-byte archive comparison.')
    print(f'Redacted {len(redactions)} copied JSON files; source response payloads unchanged.')
    print(f'Package: {archive.relative_to(ROOT).as_posix()} ({archive.stat().st_size:,} bytes)')


if __name__=='__main__': main()
