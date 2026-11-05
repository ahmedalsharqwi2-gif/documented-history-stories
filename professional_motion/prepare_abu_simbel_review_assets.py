"""Rehydrate only pinned, licensed Abu Simbel review assets; no voice or publication."""
import base64
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
def digest(data):
    return hashlib.sha256(data).hexdigest()

def prepare():
    project = ROOT / 'remotion_motion'
    public = project / 'public'
    manifest = json.loads((project / 'assets.json').read_text())
    evidence = []
    for asset in manifest['assets']:
        if asset['id'] not in {'history-lift', 'history-old', 'history-document'}:
            continue
        encoded = ''.join((project / part).read_text().strip() for part in asset['cache_parts'])
        content = base64.b64decode(encoded, validate=True)
        if digest(content) != asset['cache_sha256']:
            raise ValueError('Archival cache fingerprint differs: ' + asset['id'])
        target = public / asset['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(content)) as image:
            dimensions = image.size
            image.convert('RGB').save(target, quality=94)
        proof = {**asset, 'decoded_dimensions': dimensions, 'verified_cache_used': True,
                 'output_sha256': digest(target.read_bytes())}
        target.with_suffix('.source.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2))
        evidence.append(proof)
    world = public / 'world.json'
    source = manifest['world']
    content = world.read_bytes() if world.exists() else urlopen(source['url'], timeout=45).read()
    if digest(content) != source['sha256']:
        raise ValueError('Pinned Natural Earth bytes differ')
    world.write_bytes(content)
    # WGS84 locator only: no invented Nile curve or unsourced new/old-site distances.
    bounds, point = (20, 19, 38, 34), (31.6258, 22.3372)
    def xy(coord):
        return ((coord[0] - bounds[0]) / 18 * 700, (bounds[3] - coord[1]) / 15 * 550)
    image = Image.new('RGB', (700, 550), '#18201d')
    draw = ImageDraw.Draw(image)
    for feature in json.loads(content)['features']:
        geometry = feature['geometry']
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']] if geometry['type'] == 'Polygon' else []
        for polygon in polygons:
            draw.polygon([xy(coord) for coord in polygon[0]], fill='#69756a', outline='#fff8e8', width=2)
    x, y = xy(point)
    draw.line([(x, y - 12), (x, y - 52)], fill='#fff8e8', width=4)
    draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill='#fff8e8', outline='#18201d', width=4)
    target = public / 'review-media/geographic-context.png'
    target.parent.mkdir(exist_ok=True)
    image.save(target)
    target.with_suffix('.source.json').write_text(json.dumps({**source, 'point_wgs84': point,
        'bounds_lonlat': bounds, 'output_sha256': digest(target.read_bytes()),
        'note': 'Schematic country locator, not a topographical survey'}, indent=2))
    (public / 'history-review-assets-proof.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    return evidence

if __name__ == '__main__':
    print('Verified history assets:', len(prepare()))
