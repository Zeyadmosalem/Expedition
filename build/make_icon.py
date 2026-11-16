"""Turn assets/hero_skull.png into the multi-size Windows icon build/expedition.ico."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
logo = Image.open(root / 'assets' / 'hero_skull.png').convert('RGBA')
logo = logo.crop(logo.getbbox())
side = max(logo.size)
square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
square.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
square.save(root / 'build' / 'expedition.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
print('icon written')
