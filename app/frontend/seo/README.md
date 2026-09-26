# Source files for the generated images in `../public`

Social networks and iOS do not accept SVG, so these PNGs are rendered from SVG and committed. Run from this folder
(needs `rsvg-convert`, e.g. `brew install librsvg`):

```bash
# Social preview card (og:image / twitter:image), from og-image.svg
rsvg-convert -w 1200 -h 630 og-image.svg -o ../public/og-image.png

# Icons: the real logo (a circle on a transparent background), from ../public/logo.svg
rsvg-convert -w 180 -h 180 ../public/logo.svg -o ../public/apple-touch-icon.png
rsvg-convert -w 192 -h 192 ../public/logo.svg -o ../public/icon-192.png
rsvg-convert -w 512 -h 512 ../public/logo.svg -o ../public/icon-512.png
```
