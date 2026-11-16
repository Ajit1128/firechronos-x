#!/usr/bin/env python3
"""Compare CSVs inside original NASA FIRMS download ZIPs with our manifest.

Read-only on source ZIPs and local raw files. Writes a privacy-conscious
verification report only after *both* sources pass. No network or NASA key.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from zipfile import ZipFile, BadZipFile

MAX_ARCHIVE_BYTES = 150_000_000
MAX_CSV_BYTES = 70_000_000


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read_source(archive, filename):
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError(f'ZIP demasiado grande: {archive.name}')
    with ZipFile(archive) as z:
        matches = [i for i in z.infolist() if not i.is_dir() and Path(i.filename).name == filename]
        if len(matches) != 1:
            raise ValueError(f'{archive.name}: se esperaba exactamente un {filename}; encontrados {len(matches)}')
        member = matches[0]
        if member.file_size > MAX_CSV_BYTES:
            raise ValueError(f'CSV demasiado grande en {archive.name}')
        with z.open(member) as fd:
            raw = fd.read(MAX_CSV_BYTES + 1)
        if len(raw) > MAX_CSV_BYTES:
            raise ValueError(f'Descompresión inesperada en {archive.name}')
    return raw


def main():
    p = argparse.ArgumentParser(description='Verificar archivos NASA FIRMS 850535 y 850536 por SHA-256')
    p.add_argument('--modis-zip', type=Path, required=True)
    p.add_argument('--viirs-zip', type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=Path('docs/evidence/panama_march_2024_manifest.json'))
    p.add_argument('--raw-root', type=Path, help='Directorio data/raw para comprobar también los CSV extraídos')
    p.add_argument('--report', type=Path, default=Path('docs/evidence/nasa_archive_hash_verification.json'))
    args = p.parse_args()
    for path in [args.modis_zip, args.viirs_zip, args.manifest]:
        if not path.is_file():
            p.error(f'No existe {path}')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if (manifest.get('archive_request_ids') != {'MODIS': '850535', 'VIIRS_SNPP': '850536'}
            or manifest.get('period_start') != '2024-03-01'
            or manifest.get('period_end') != '2024-03-31'):
        p.error('Identificadores/periodos del manifiesto no coinciden: comprobar manualmente.')
    sources = {s['sensor']: s for s in manifest['sources']}
    report = {
        'result': 'all_files_equal_to_manifest_by_sha256',
        'method': 'SHA256 de CSV dentro de ZIP original, cotejado contra manifiesto local',
        'limitation': 'Requiere conservar correos NASA y evidencia de descarga oficial; hashes locales no autentican el servidor externo por sí solos.',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'request_ids': manifest['archive_request_ids'],
        'period_start': manifest['period_start'],
        'period_end': manifest['period_end'],
        'sources': [],
    }
    for sensor, archive in [('MODIS', args.modis_zip), ('VIIRS_SNPP', args.viirs_zip)]:
        source = sources[sensor]
        file_name = source['file']
        raw = read_source(archive, file_name)
        actual = sha256(raw)
        expected = source['sha256'].lower()
        if actual != expected:
            raise ValueError(f'ERROR {sensor}: SHA CSV ORIGINAL {actual} != manifiesto {expected}. No se genera informe.')
        entry = {
            'sensor': sensor,
            'request_id': manifest['archive_request_ids'][sensor],
            'archive_filename': archive.name,
            'archive_zip_sha256': sha256(archive.read_bytes()),
            'original_csv_filename': file_name,
            'csv_sha256': actual,
            'matches_manifest': True,
            'archive_csv_size_bytes': len(raw),
        }
        if args.raw_root:
            if not args.raw_root.is_dir():
                raise ValueError(f'No existe raw-root: {args.raw_root}')
            files = list(args.raw_root.rglob(file_name))
            if len(files) != 1:
                raise ValueError(f'Se esperaba un CSV {file_name} bajo raw-root; encontrados {len(files)}')
            extracted_hash = sha256(files[0].read_bytes())
            if extracted_hash != actual:
                raise ValueError(f'ERROR {sensor}: CSV extraído no coincide con el ZIP NASA original.')
            entry['extracted_raw_csv_matches_archive'] = True
        report['sources'].append(entry)
        print(f'OK {sensor}: SHA-256 original = manifiesto ({actual})')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('VERIFICACION NASA FIRMS OK; informe:', args.report)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, BadZipFile, OSError) as exc:
        raise SystemExit('VERIFICACION FALLIDA: ' + str(exc)) from exc
